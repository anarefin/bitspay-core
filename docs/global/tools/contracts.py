#!/usr/bin/env python3
"""Bits Pay v6 contract tool — producer-owned contracts, consumer pins.

Usage (run from anywhere; paths resolve relative to this file):
  contracts.py check [svc ...]            validate packs (all when none given)
  contracts.py snapshot <svc|all>         copy pinned producer artefacts into <svc>/contracts/consumed/, build stubs + fixtures
  contracts.py index                      regenerate 00-global/DEPENDENCY-INDEX.md, SYSTEM-CONTEXT.md, generated/*.json
  contracts.py impact <svc> <artefact>[#field]
        artefact = "METHOD /path" | <topic>/<EVENT_TYPE> | codes/<set>[#value] | data/<id>
  contracts.py cr new <svc> "<title>"
  contracts.py cr analyse <CR-id>
  contracts.py cr verify <CR-id>
  contracts.py cr log

Requires Python 3.9+ and PyYAML. No other dependency (a small JSON-Schema subset validator is built in).
See 00-global/CONTRACT-MODEL.md and CHANGE-PROCESS.md.
"""
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
GLOBAL = os.path.dirname(HERE)
ROOT = os.path.dirname(GLOBAL)
SERVICES = os.path.join(ROOT, "services")
GENERATED = os.path.join(GLOBAL, "generated")
HTTP_METHODS = ("get", "post", "put", "patch", "delete")
# operations every maker-checker service serves (kernel K5) — duplicates across packs are expected
KERNEL_PATTERN_PATHS = {"/v1/approvals", "/v1/approvals/{id}:approve", "/v1/approvals/{id}:reject",
                        "/v1/approvals/{approvalId}:approve", "/v1/approvals/{approvalId}:reject"}
KERNEL_DIAGRAMS = ("flowchart", "graph", "sequenceDiagram", "stateDiagram", "stateDiagram-v2", "erDiagram",
                   "classDiagram", "gantt", "journey", "timeline", "mindmap", "C4Context", "C4Container", "block-beta")


# ----------------------------------------------------------------------------- helpers
def rel(p):
    return os.path.relpath(p, ROOT)


def load_yaml(p):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def norm_op(op):
    m = re.match(r"^\s*([A-Za-z]+)\s+(\S+)\s*$", op or "")
    if not m:
        return None
    return m.group(1).upper() + " " + m.group(2)


def op_shape(op):
    """'GET /v1/wallets/{walletId}' -> 'GET /v1/wallets/{}' (path-param names ignored for matching)."""
    return re.sub(r"\{[^}]+\}", "{}", op)


def file_hash(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def pack_hash(pack_dir):
    """Hash of everything in a pack except changes/ (CR files) — used for diff-scope checks."""
    h = hashlib.sha256()
    for base, dirs, files in sorted(os.walk(pack_dir)):
        dirs[:] = sorted(d for d in dirs if d != "changes" and not d.startswith("."))
        for fn in sorted(files):
            if fn.startswith("."):
                continue
            p = os.path.join(base, fn)
            h.update(os.path.relpath(p, pack_dir).encode())
            h.update(file_hash(p).encode())
    return h.hexdigest()


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append("%s: %s" % (where, msg))

    def warn(self, where, msg):
        self.warnings.append("%s: %s" % (where, msg))


# ----------------------------------------------------------------------------- JSON-schema subset
class SchemaDoc:
    """A schema document with local $ref resolution (#/components/schemas/X, #/$defs/X)."""

    def __init__(self, doc, name):
        self.doc, self.name = doc, name

    def deref(self, s, depth=0):
        while isinstance(s, dict) and "$ref" in s and depth < 30:
            ref = s["$ref"]
            if not ref.startswith("#/"):
                return {}  # external refs (kernel schemas) are treated as opaque
            node = self.doc
            for part in ref[2:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                if not isinstance(node, dict) or part not in node:
                    raise KeyError("unresolvable $ref %s in %s" % (ref, self.name))
                node = node[part]
            s, depth = node, depth + 1
        return s

    def branches(self, s):
        """Flatten allOf/oneOf/anyOf into a list of concrete sub-schemas."""
        s = self.deref(s)
        if not isinstance(s, dict):
            return []
        out = [s]
        for k in ("allOf", "oneOf", "anyOf"):
            for sub in s.get(k, []) or []:
                out.extend(self.branches(sub))
        return out

    def has_path(self, s, segments):
        """True / False / None (None = schema too loose to tell)."""
        if not segments:
            return True
        seg = segments[0]
        is_arr = seg.endswith("[]")
        key = seg[:-2] if is_arr else seg
        loose = False
        for b in self.branches(s):
            props = b.get("properties") or {}
            if key in props:
                child = props[key]
                if is_arr:
                    found_items = False
                    for cb in self.branches(child):
                        if "items" in cb:
                            found_items = True
                            r = self.has_path(cb["items"], segments[1:])
                            if r:
                                return True
                            if r is None:
                                loose = True
                    if not found_items:
                        loose = True
                    continue
                r = self.has_path(child, segments[1:])
                if r:
                    return True
                if r is None:
                    loose = True
            elif not props and (b.get("type") in (None, "object") or b.get("additionalProperties") not in (None, False)):
                ap = b.get("additionalProperties")
                if isinstance(ap, dict):
                    r = self.has_path(ap, segments[1:])
                    if r is None or r:
                        loose = True
                elif "allOf" not in b and "oneOf" not in b and "anyOf" not in b and "$ref" not in b:
                    loose = True
        return None if loose else False


def split_path(p):
    return [x for x in re.split(r"\.(?![^\[]*\])", p) if x]


TYPE_CHECK = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate(sd, schema, value, path="$", errs=None, depth=0):
    errs = [] if errs is None else errs
    if depth > 40:
        return errs
    try:
        s = sd.deref(schema)
    except KeyError as e:
        errs.append(str(e))
        return errs
    if not isinstance(s, dict) or s is True:
        return errs
    for sub in s.get("allOf", []) or []:
        validate(sd, sub, value, path, errs, depth + 1)
    for k in ("oneOf", "anyOf"):
        if s.get(k):
            ok = any(not validate(sd, sub, value, path, [], depth + 1) for sub in s[k])
            if not ok:
                errs.append("%s: matches none of %s" % (path, k))
    t = s.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(TYPE_CHECK.get(tt, lambda v: True)(value) for tt in types):
            errs.append("%s: expected %s, got %s" % (path, "|".join(types), type(value).__name__))
            return errs
    if "const" in s and value != s["const"]:
        errs.append("%s: expected const %r" % (path, s["const"]))
    if "enum" in s and value not in s["enum"]:
        errs.append("%s: %r not in enum" % (path, value))
    if isinstance(value, str) and "pattern" in s:
        try:
            if not re.search(s["pattern"], value):
                errs.append("%s: %r does not match %s" % (path, value, s["pattern"]))
        except re.error:
            pass
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in s and value < s["minimum"]:
            errs.append("%s: below minimum" % path)
        if "maximum" in s and value > s["maximum"]:
            errs.append("%s: above maximum" % path)
    if isinstance(value, dict):
        for r in s.get("required", []) or []:
            if r not in value:
                errs.append("%s: missing required %s" % (path, r))
        props = s.get("properties") or {}
        for k, v in value.items():
            if k in props:
                validate(sd, props[k], v, path + "." + k, errs, depth + 1)
            elif s.get("additionalProperties") is False:
                errs.append("%s: unexpected property %s" % (path, k))
            elif isinstance(s.get("additionalProperties"), dict):
                validate(sd, s["additionalProperties"], v, path + "." + k, errs, depth + 1)
    if isinstance(value, list) and "items" in s:
        for i, v in enumerate(value):
            validate(sd, s["items"], v, "%s[%d]" % (path, i), errs, depth + 1)
    return errs


# ----------------------------------------------------------------------------- model
class Pack:
    def __init__(self, folder):
        self.folder = folder
        self.dir = os.path.join(SERVICES, folder)
        self.cdir = os.path.join(self.dir, "contracts")
        self.manifest_path = os.path.join(self.cdir, "contract.yaml")
        self.ok = os.path.exists(self.manifest_path)
        self.m = load_yaml(self.manifest_path) if self.ok else {}
        self.m = self.m or {}
        self.service = self.m.get("service") or re.sub(r"^\d+-", "", folder)
        self.ops = {}          # "METHOD /path" -> (opobj, pathitem, SchemaDoc)
        self.events = {}       # (topic, type, version) -> dict(schema=SchemaDoc, root, path, meta)
        self.topic_meta = {}   # topic -> provides entry
        self.codes = {}
        self.data = {}         # id -> entry
        self.openapi_docs = []

    @property
    def provides(self):
        return self.m.get("provides") or {}

    @property
    def consumes(self):
        return self.m.get("consumes") or {}

    def p(self, relpath):
        return os.path.join(self.cdir, relpath)


def load_packs(rep=None):
    packs = {}
    if not os.path.isdir(SERVICES):
        return packs
    for folder in sorted(os.listdir(SERVICES)):
        if folder.startswith(".") or not os.path.isdir(os.path.join(SERVICES, folder)):
            continue
        pk = Pack(folder)
        if not pk.ok:
            if rep:
                rep.warn(folder, "no contracts/contract.yaml yet")
            continue
        try:
            index_pack(pk, rep)
        except Exception as e:  # keep going, report
            if rep:
                rep.err(folder, "failed to index: %s" % e)
        packs[pk.service] = pk
    return packs


def index_pack(pk, rep):
    where = pk.folder
    for api in pk.provides.get("apis") or []:
        path = pk.p(api.get("openapi", "provided/openapi.yaml"))
        if not os.path.exists(path):
            rep and rep.err(where, "openapi missing: %s" % rel(path))
            continue
        try:
            doc = load_yaml(path)
        except Exception as e:
            rep and rep.err(where, "openapi does not parse: %s" % e)
            continue
        sd = SchemaDoc(doc, rel(path))
        pk.openapi_docs.append((path, doc))
        for p, item in (doc.get("paths") or {}).items():
            for meth in HTTP_METHODS:
                if isinstance(item, dict) and meth in item:
                    pk.ops["%s %s" % (meth.upper(), p)] = (item[meth], item, sd)
    for kind in ("events", "inboundTopics"):
        for t in pk.provides.get(kind) or []:
            topic = t.get("topic")
            pk.topic_meta[topic] = dict(t, _kind=kind)
            for et in t.get("eventTypes") or []:
                sp = pk.p(et.get("schema", ""))
                entry = {"meta": et, "path": sp, "topic": topic, "kind": kind}
                if os.path.exists(sp):
                    try:
                        d = load_json(sp)
                        entry["schema"] = SchemaDoc(d, rel(sp))
                        entry["root"] = d
                    except Exception as e:
                        rep and rep.err(where, "schema does not parse %s: %s" % (rel(sp), e))
                else:
                    rep and rep.err(where, "schema missing %s" % rel(sp))
                pk.events[(topic, et.get("type"), int(et.get("version", 1)))] = entry
    cp = pk.provides.get("codes")
    if cp:
        path = pk.p(cp)
        if os.path.exists(path):
            try:
                pk.codes = load_yaml(path) or {}
            except Exception as e:
                rep and rep.err(where, "codes.yaml does not parse: %s" % e)
        else:
            rep and rep.err(where, "codes file missing %s" % rel(path))
    for d in pk.provides.get("data") or []:
        pk.data[d.get("id")] = d


# ----------------------------------------------------------------------------- field resolution
def find_op(producer, op):
    op = norm_op(op)
    if not op:
        return None, None
    if op in producer.ops:
        return op, producer.ops[op]
    shape = op_shape(op)
    for k, v in producer.ops.items():
        if op_shape(k) == shape:
            return k, v
    return None, None


def op_has_field(opentry, field):
    opobj, item, sd = opentry
    if field == "*":
        return True
    prefix, _, rest = field.partition(".")
    if prefix in ("path", "query", "header"):
        params = list(item.get("parameters") or []) + list(opobj.get("parameters") or [])
        for prm in params:
            prm = sd.deref(prm)
            if prm.get("in") == prefix and prm.get("name", "").lower() == rest.lower():
                return True
        if prefix == "header":
            return None  # headers are often kernel-level (K3.1) — not provable
        return False
    if prefix == "req":
        rb = sd.deref(opobj.get("requestBody") or {})
        content = rb.get("content") or {}
        schemas = [c.get("schema") for c in content.values() if isinstance(c, dict) and c.get("schema")]
        if not schemas:
            return False
        res = [sd.has_path(s, split_path(rest)) for s in schemas]
        return True if any(r is True for r in res) else (None if any(r is None for r in res) else False)
    if prefix in ("res", "problem"):
        out = []
        for code, resp in (opobj.get("responses") or {}).items():
            code = str(code)
            if prefix == "res" and not code.startswith("2"):
                continue
            if prefix == "problem" and code.startswith("2"):
                continue
            resp = sd.deref(resp)
            for ct, c in (resp.get("content") or {}).items():
                if isinstance(c, dict) and c.get("schema") is not None:
                    out.append(sd.has_path(c["schema"], split_path(rest)))
        if not out:
            return None if prefix == "problem" else False
        return True if any(r is True for r in out) else (None if any(r is None for r in out) else False)
    return False


def event_has_field(entry, field):
    if field == "*":
        return True
    if "schema" not in entry:
        return None
    return entry["schema"].has_path(entry["root"], split_path(field))


# ----------------------------------------------------------------------------- check
def check(names=None):
    rep = Report()
    packs = load_packs(rep)
    selected = [p for p in packs.values() if not names or p.service in names or p.folder in names]
    if names and not selected:
        rep.err("check", "no pack matches %s" % names)

    # ---- global uniqueness
    topic_owner, group_owner, prefix_owner, op_owner = {}, {}, {}, {}
    for pk in packs.values():
        for t, meta in pk.topic_meta.items():
            if t in topic_owner and topic_owner[t] != pk.service:
                rep.err(pk.folder, "topic %s also provided by %s" % (t, topic_owner[t]))
            topic_owner[t] = pk.service
        for op in pk.ops:
            path = op.split(" ", 1)[1]
            if path in KERNEL_PATTERN_PATHS:
                continue
            sh = op_shape(op)
            if sh in op_owner and op_owner[sh] != pk.service:
                rep.err(pk.folder, "operation %s also provided by %s" % (op, op_owner[sh]))
            op_owner[sh] = pk.service
        for pr in (pk.codes.get("txnRefPrefixes") or []):
            px = pr.get("prefix") if isinstance(pr, dict) else pr
            if px in prefix_owner and prefix_owner[px] != pk.service:
                rep.err(pk.folder, "txnRef prefix %s also minted by %s" % (px, prefix_owner[px]))
            prefix_owner[px] = pk.service
        for kind in ("events", "inboundTopics"):
            for c in pk.consumes.get(kind) or []:
                g = c.get("groupId")
                if kind == "events" and g:
                    if not re.match(r"^%s(\.[a-z0-9${}A-Z_-]+)?$" % re.escape(pk.service), g):
                        rep.err(pk.folder, "groupId %s does not match ^<service>(.<purpose>)?$ (kernel K4.3)" % g)
                    key = (g, c.get("topic"))
                    if g in group_owner and group_owner[g][0] != pk.service:
                        rep.err(pk.folder, "groupId %s also used by %s" % (g, group_owner[g][0]))
                    group_owner[g] = (pk.service, c.get("topic"))

    for pk in selected:
        check_pack(pk, packs, rep)

    for w in rep.warnings:
        print("WARN  " + w)
    for e in rep.errors:
        print("ERROR " + e)
    print("\n%d pack(s) checked · %d error(s) · %d warning(s)" % (len(selected), len(rep.errors), len(rep.warnings)))
    return 1 if rep.errors else 0


def check_pack(pk, packs, rep):
    w = pk.folder
    m = pk.m
    for k in ("service", "contractVersion", "kernel", "provides", "consumes"):
        if k not in m:
            rep.err(w, "contract.yaml missing key '%s'" % k)
    if not re.match(r"^\d+\.\d+\.\d+$", str(m.get("contractVersion", ""))):
        rep.err(w, "contractVersion must be semver x.y.z")
    if not re.match(r"^\d+-%s$" % re.escape(pk.service), pk.folder):
        rep.warn(w, "folder name does not end with service name %s" % pk.service)
    # O2: producers never list consumers
    for kind in ("events", "inboundTopics"):
        for t in pk.provides.get(kind) or []:
            if "consumers" in t:
                rep.err(w, "provides.%s[%s] lists consumers (rule O2)" % (kind, t.get("topic")))
    # all json parse + examples validate
    for base, _, files in os.walk(os.path.join(pk.cdir, "provided")):
        for fn in files:
            p = os.path.join(base, fn)
            if fn.endswith(".json"):
                try:
                    load_json(p)
                except Exception as e:
                    rep.err(w, "invalid JSON %s: %s" % (rel(p), e))
    env_schema = load_json(os.path.join(GLOBAL, "schemas", "envelope.schema.json"))
    env_sd = SchemaDoc(env_schema, "envelope")
    for (topic, et, ver), entry in pk.events.items():
        ex = entry["path"].replace(".schema.json", ".example.json")
        if not os.path.exists(ex):
            rep.warn(w, "no example for %s/%s v%d" % (topic, et, ver))
            continue
        try:
            env = load_json(ex)
        except Exception as e:
            rep.err(w, "example does not parse %s: %s" % (rel(ex), e))
            continue
        for e in validate(env_sd, env_schema, env):
            rep.err(w, "%s envelope: %s" % (rel(ex), e))
        if entry["kind"] == "events" and env.get("producer") not in (pk.service,):
            rep.err(w, "%s producer %r != %s" % (rel(ex), env.get("producer"), pk.service))
        if env.get("eventType") != et:
            rep.err(w, "%s eventType %r != %s" % (rel(ex), env.get("eventType"), et))
        if "schema" in entry:
            for e in validate(entry["schema"], entry["root"], env.get("data", {})):
                rep.err(w, "%s data: %s" % (rel(ex), e))
    # openapi sanity
    for path, doc in pk.openapi_docs:
        if not str(doc.get("openapi", "")).startswith("3.1"):
            rep.warn(w, "%s is not OpenAPI 3.1" % rel(path))
        sd = SchemaDoc(doc, rel(path))
        for op, (opobj, item, _) in pk.ops.items():
            if "x-audience" not in opobj:
                rep.warn(w, "%s has no x-audience" % op)
        # resolve all refs once
        def walk(n):
            if isinstance(n, dict):
                if "$ref" in n:
                    try:
                        sd.deref(n)
                    except KeyError as e:
                        rep.err(w, str(e))
                for v in n.values():
                    walk(v)
            elif isinstance(n, list):
                for v in n:
                    walk(v)
        walk(doc)
    # consumes
    c = pk.consumes
    for api in c.get("apis") or []:
        prod = packs.get(api.get("producer"))
        where = "%s consumes %s %s" % (w, api.get("producer"), api.get("operation"))
        if not prod:
            rep.err(where, "producer pack not found")
            continue
        real, entry = find_op(prod, api.get("operation"))
        if not entry:
            rep.err(where, "operation not provided by %s" % prod.service)
            continue
        if real != norm_op(api.get("operation")):
            rep.warn(where, "path-parameter names differ from provider (%s)" % real)
        check_pin(api, prod, where, rep)
        for f in api.get("fieldsUsed") or []:
            r = op_has_field(entry, f)
            if r is False:
                rep.err(where, "fieldsUsed '%s' not in provider contract" % f)
            elif r is None:
                rep.warn(where, "fieldsUsed '%s' cannot be proven (loose schema)" % f)
        check_codes_used(api, prod, where, rep, packs)
    for kind in ("events", "inboundTopics"):
        for ev in c.get(kind) or []:
            owner = ev.get("producer") or ev.get("owner")
            prod = packs.get(owner)
            where = "%s consumes %s %s/%s" % (w, owner, ev.get("topic"), ev.get("eventType"))
            if not prod:
                rep.err(where, "producer pack not found")
                continue
            key = (ev.get("topic"), ev.get("eventType"), int(ev.get("version", 1)))
            entry = prod.events.get(key)
            if not entry:
                rep.err(where, "event %s v%s not provided by %s" % (key[1], key[2], owner))
                continue
            check_pin(ev, prod, where, rep)
            for f in ev.get("fieldsUsed") or []:
                r = event_has_field(entry, f)
                if r is False:
                    rep.err(where, "fieldsUsed '%s' not in producer schema" % f)
                elif r is None:
                    rep.warn(where, "fieldsUsed '%s' cannot be proven (loose schema)" % f)
            check_codes_used(ev, prod, where, rep, packs)
            for tc in ev.get("templates") or []:
                own = {t.get("code") for t in (pk.codes.get("notificationTemplates") or []) if isinstance(t, dict)}
                if tc not in own:
                    rep.err(where, "sends template %s that is not declared in own codes.yaml" % tc)
    for d in c.get("data") or []:
        prod = packs.get(d.get("producer"))
        where = "%s consumes data %s/%s" % (w, d.get("producer"), d.get("id"))
        if not prod or d.get("id") not in prod.data:
            rep.err(where, "data contract not provided")
            continue
        check_pin(d, prod, where, rep)
    for cs in c.get("codes") or []:
        prod = packs.get(cs.get("producer"))
        where = "%s consumes codes %s/%s" % (w, cs.get("producer"), cs.get("set"))
        if not prod:
            rep.err(where, "producer pack not found")
            continue
        check_codes_used({"codesUsed": [cs]}, prod, where, rep, packs)
    # SPEC.md / CLAUDE.md
    spec = os.path.join(pk.dir, "SPEC.md")
    if not os.path.exists(spec):
        rep.err(w, "SPEC.md missing")
    else:
        lint_spec(pk, spec, rep)
    if not os.path.exists(os.path.join(pk.dir, "CLAUDE.md")):
        rep.err(w, "CLAUDE.md missing")


def check_pin(entry, prod, where, rep):
    pinned = str(entry.get("pinnedContractVersion", ""))
    cur = str(prod.m.get("contractVersion", ""))
    if not pinned:
        rep.err(where, "pinnedContractVersion missing")
        return
    try:
        pmaj, cmaj = int(pinned.split(".")[0]), int(cur.split(".")[0])
        if pmaj != cmaj:
            rep.warn(where, "pinned %s, producer now %s (major differs — re-pin when ready)" % (pinned, cur))
    except ValueError:
        rep.err(where, "bad version %s / %s" % (pinned, cur))


def code_values(prod, setname):
    if setname and setname.startswith("reason:"):  # a reasonCodes group, e.g. "reason:Hold"
        grp = setname[7:].strip().lower()
        for g in prod.codes.get("reasonCodes") or []:
            if str(g.get("group", "")).lower() == grp:
                return {str(v.get("code") if isinstance(v, dict) else v) for v in g.get("values") or []}
        return None
    if setname == "entityTypes":
        vals = set()
        for e in prod.codes.get("entityTypes") or []:
            vals.update(e.get("values") or [])
        return vals
    sets = prod.codes.get("codeSets") or {}
    if setname not in sets:
        return None
    vals = set()
    for v in sets[setname].get("values") or []:
        if isinstance(v, dict):
            vals.add(str(v.get("code")))
            if v.get("name"):
                vals.add(str(v.get("name")))
        else:
            vals.add(str(v))
    return vals


def check_codes_used(entry, prod, where, rep, packs=None):
    for cu in entry.get("codesUsed") or []:
        if cu.get("producer") and packs is not None:
            prod = packs.get(cu["producer"]) or prod  # a code set owned by another service than the artefact's producer
        vals = code_values(prod, cu.get("set"))
        if vals is None:
            rep.err(where, "code set '%s' not in %s codes.yaml" % (cu.get("set"), prod.service))
            continue
        want = cu.get("values")
        if want and want != "*":
            for v in want:
                if str(v) not in vals:
                    rep.err(where, "code '%s' not in %s.%s" % (v, prod.service, cu.get("set")))


FORBIDDEN_REFS = [
    (r"03-Contract-Catalogue|Contract Catalogue|catalogue §|CONTRACTS\.md", "references the old central catalogue"),
    (r"v5\.0 overlay|Catalogue v1\.1 alignment|Part 0", "overlay text left in"),
    (r"\bmvnw\b|pom\.xml", "Maven remnants"),
]


def lint_spec(pk, spec, rep):
    w = pk.folder + "/SPEC.md"
    with open(spec, encoding="utf-8") as f:
        text = f.read()
    for i in range(1, 15):
        if not re.search(r"^## %d\. " % i, text, re.M):
            rep.warn(w, "section '## %d.' not found" % i)
    for pat, msg in FORBIDDEN_REFS:
        hits = [m.start() for m in re.finditer(pat, text)]
        prov = text.find("Provenance")
        hits = [h for h in hits if prov < 0 or h < prov]
        if hits:
            ln = text.count("\n", 0, hits[0]) + 1
            rep.warn(w, "%s (first at line %d, %d hit(s))" % (msg, ln, len(hits)))
    blocks = re.findall(r"```mermaid\n(.*?)```", text, re.S)
    if len(blocks) < 3:
        rep.warn(w, "only %d mermaid diagram(s)" % len(blocks))
    for b in blocks:
        first = next((l.strip() for l in b.splitlines() if l.strip() and not l.strip().startswith("%%")), "")
        if not first.split(" ")[0] in KERNEL_DIAGRAMS:
            rep.err(w, "mermaid block starts with unknown type: %r" % first[:40])
        if first.startswith(("flowchart", "graph")):
            for ln in b.splitlines():
                if ln.count('"') % 2 == 1:
                    rep.err(w, "mermaid: unbalanced quotes: %r" % ln.strip()[:80])
                    break
    if "OPEN D-" in text and not re.search(r"^## 13\.", text, re.M):
        rep.err(w, "OPEN D-xx tags used but §13 missing")


# ----------------------------------------------------------------------------- snapshot / stubs / fixtures
def snapshot(name):
    packs = load_packs(Report())
    targets = list(packs.values()) if name == "all" else [p for p in packs.values() if name in (p.service, p.folder)]
    if not targets:
        sys.exit("no pack %s" % name)
    for pk in targets:
        out = os.path.join(pk.cdir, "consumed")
        if os.path.isdir(out):
            shutil.rmtree(out)
        os.makedirs(out)
        stubs = os.path.join(pk.dir, "stubs")
        if os.path.isdir(stubs):
            for d in os.listdir(stubs):
                if os.path.isdir(os.path.join(stubs, d)) and d in packs:
                    shutil.rmtree(os.path.join(stubs, d))
        lock = {"service": pk.service, "generatedAt": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "pins": []}
        c = pk.consumes
        by_prod = {}
        for api in c.get("apis") or []:
            by_prod.setdefault(api.get("producer"), {"apis": [], "events": [], "data": [], "codes": False})["apis"].append(api)
        for kind in ("events", "inboundTopics"):
            for ev in c.get(kind) or []:
                by_prod.setdefault(ev.get("producer") or ev.get("owner"), {"apis": [], "events": [], "data": [], "codes": False})["events"].append(ev)
        for d in c.get("data") or []:
            by_prod.setdefault(d.get("producer"), {"apis": [], "events": [], "data": [], "codes": False})["data"].append(d)
        for cs in c.get("codes") or []:
            by_prod.setdefault(cs.get("producer"), {"apis": [], "events": [], "data": [], "codes": False})["codes"] = True
        for prod_name, use in sorted(by_prod.items()):
            prod = packs.get(prod_name)
            if not prod:
                print("WARN %s: producer %s not found — skipped" % (pk.service, prod_name))
                continue
            pdir = os.path.join(out, prod_name)
            os.makedirs(pdir, exist_ok=True)
            if use["apis"]:
                src = prod.p("provided/openapi.yaml")
                shutil.copy2(src, os.path.join(pdir, "openapi.yaml"))
                write_stubs(pk, prod, use["apis"])
            for ev in use["events"]:
                key = (ev.get("topic"), ev.get("eventType"), int(ev.get("version", 1)))
                entry = prod.events.get(key)
                if not entry:
                    continue
                dst = os.path.join(pdir, "events", ev.get("topic"))
                os.makedirs(dst, exist_ok=True)
                shutil.copy2(entry["path"], dst)
                ex = entry["path"].replace(".schema.json", ".example.json")
                if os.path.exists(ex):
                    shutil.copy2(ex, dst)
                    fx = os.path.join(pk.dir, "fixtures", "events")
                    os.makedirs(fx, exist_ok=True)
                    with open(ex, encoding="utf-8") as f:
                        line = json.dumps(json.load(f), separators=(",", ":"))
                    with open(os.path.join(fx, "%s.%s.v%d.jsonl" % key), "w", encoding="utf-8") as f:
                        f.write(line + "\n")
            for d in use["data"]:
                e = prod.data.get(d.get("id"))
                if e:
                    dst = os.path.join(pdir, "data")
                    os.makedirs(dst, exist_ok=True)
                    shutil.copy2(prod.p(e.get("file")), dst)
            if prod.codes:
                shutil.copy2(prod.p(prod.provides.get("codes")), os.path.join(pdir, "codes.yaml"))
            lock["pins"].append({"producer": prod_name, "pinnedContractVersion": min(
                [str(x.get("pinnedContractVersion")) for x in use["apis"] + use["events"] + use["data"]] or ["?"]),
                "producerContractVersionAtSnapshot": prod.m.get("contractVersion")})
        # own produced fixtures
        fx = os.path.join(pk.dir, "fixtures", "events")
        os.makedirs(fx, exist_ok=True)
        for key, entry in pk.events.items():
            ex = entry["path"].replace(".schema.json", ".example.json")
            if os.path.exists(ex):
                with open(ex, encoding="utf-8") as f:
                    line = json.dumps(json.load(f), separators=(",", ":"))
                with open(os.path.join(fx, "%s.%s.v%d.jsonl" % key), "w", encoding="utf-8") as f:
                    f.write(line + "\n")
        with open(os.path.join(out, "PINS.lock"), "w", encoding="utf-8") as f:
            yaml.safe_dump(lock, f, sort_keys=False)
        print("snapshot %-28s %d producer(s)" % (pk.service, len(by_prod)))


def example_of(sd, node):
    node = sd.deref(node or {})
    if not isinstance(node, dict):
        return None
    for c in (node.get("content") or {}).values():
        if not isinstance(c, dict):
            continue
        if "example" in c:
            return c["example"]
        if c.get("examples"):
            first = list(c["examples"].values())[0]
            first = sd.deref(first)
            return first.get("value")
        sch = sd.deref(c.get("schema") or {})
        if isinstance(sch, dict) and "example" in sch:
            return sch["example"]
    return None


def write_stubs(pk, prod, apis):
    sdir = os.path.join(pk.dir, "stubs", prod.service)
    os.makedirs(sdir, exist_ok=True)
    for api in apis:
        real, entry = find_op(prod, api.get("operation"))
        if not entry:
            continue
        opobj, item, sd = entry
        meth, path = real.split(" ", 1)
        url_pattern = "^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(path)) + "(\\?.*)?$"
        for code, resp in sorted((opobj.get("responses") or {}).items(), key=lambda kv: str(kv[0])):
            code = str(code)
            if not re.match(r"^\d{3}$", code):
                continue
            body = example_of(sd, resp)
            if body is None and not code.startswith("2"):
                continue
            ct = "application/json" if code.startswith("2") else "application/problem+json"
            mapping = {
                "name": "%s %s → %s" % (meth, path, code),
                "priority": 5 if code.startswith("2") else 9,
                "request": {"method": meth, "urlPattern": url_pattern},
                "response": {"status": int(code), "headers": {"Content-Type": ct}},
                "metadata": {"generatedBy": "contracts.py snapshot", "producer": prod.service,
                             "producerContractVersion": prod.m.get("contractVersion")},
            }
            if not code.startswith("2"):
                mapping["request"]["headers"] = {"X-Stub-Scenario": {"equalTo": code}}
            if body is not None:
                mapping["response"]["jsonBody"] = body
            slug = re.sub(r"[^a-z0-9]+", "-", ("%s-%s-%s" % (meth, path, code)).lower()).strip("-")
            with open(os.path.join(sdir, slug + ".json"), "w", encoding="utf-8") as f:
                json.dump(mapping, f, indent=2, ensure_ascii=False)
                f.write("\n")


# ----------------------------------------------------------------------------- impact
def parse_artefact(a):
    a = a.strip()
    field = None
    if "#" in a:
        a, field = a.split("#", 1)
    if re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s", a, re.I):
        return ("api", norm_op(a), field)
    if a.startswith("codes/"):
        return ("codes", a[6:], field)
    if a.startswith("data/"):
        return ("data", a[5:], field)
    if a == "internal":
        return ("internal", None, None)
    if "/" in a:
        topic, et = a.split("/", 1)
        return ("event", (topic, et), field)
    return ("unknown", a, field)


def field_matches(used, field):
    if field is None or used == "*":
        return True
    u = used.split(".", 1)[1] if used.split(".", 1)[0] in ("req", "res", "problem", "path", "query", "header") and not field.startswith(used.split(".", 1)[0] + ".") else used
    f = field
    for cand in (used, u):
        if cand == f or cand.startswith(f + ".") or cand.startswith(f + "[]") or f.startswith(cand + ".") or f.startswith(cand + "[]"):
            return True
    return False


def impact(svc, artefact, packs=None, quiet=False):
    packs = packs or load_packs(Report())
    prod = packs.get(svc) or next((p for p in packs.values() if p.folder == svc), None)
    if not prod:
        sys.exit("unknown service %s" % svc)
    kind, ident, field = parse_artefact(artefact)
    hits, misses = [], []
    additive = False
    if field:  # a field that does not exist yet in the producer's current artefact = an addition (tolerant readers)
        exists = None
        if kind == "api":
            _, entry = find_op(prod, ident)
            exists = op_has_field(entry, field) if entry else None
        elif kind == "event":
            entry = next((e for (t_, et, v), e in prod.events.items() if (t_, et) == ident), None)
            exists = event_has_field(entry, field) if entry else None
        elif kind == "codes":
            vals = code_values(prod, ident)
            exists = (field in vals) if vals is not None else None
        additive = exists is False
    for pk in packs.values():
        if pk.service == prod.service:
            continue
        c = pk.consumes
        if kind == "api":
            for api in c.get("apis") or []:
                if api.get("producer") != prod.service or op_shape(norm_op(api.get("operation")) or "") != op_shape(ident):
                    continue
                m = [u for u in api.get("fieldsUsed") or [] if field_matches(u, field)]
                (hits if (m or field is None) else misses).append((pk, "api %s" % api.get("operation"), m or ["(all)"], api))
        elif kind == "event":
            for k in ("events", "inboundTopics"):
                for ev in c.get(k) or []:
                    if (ev.get("producer") or ev.get("owner")) != prod.service:
                        continue
                    if (ev.get("topic"), ev.get("eventType")) != ident and not (ident[1] == "*" and ev.get("topic") == ident[0]):
                        continue
                    m = [u for u in ev.get("fieldsUsed") or [] if field_matches(u, field)]
                    (hits if (m or field is None) else misses).append((pk, "%s %s/%s" % (k, ev.get("topic"), ev.get("eventType")), m or ["(all)"], ev))
        elif kind == "codes":
            entries = []
            for k in ("apis", "events", "inboundTopics", "codes"):
                for e in c.get(k) or []:
                    for cu in (e.get("codesUsed") or ([e] if k == "codes" else [])):
                        owner = cu.get("producer") or e.get("producer") or e.get("owner")
                        if owner == prod.service and cu.get("set") == ident:
                            entries.append((e, cu))
            for e, cu in entries:
                vals = cu.get("values")
                hit = field is None or vals == "*" or (vals and field in [str(v) for v in vals])
                (hits if hit else misses).append((pk, "codes %s" % ident, [str(vals)], e))
        elif kind == "data":
            for d in c.get("data") or []:
                if d.get("producer") == prod.service and d.get("id") == ident:
                    hits.append((pk, "data %s" % ident, d.get("fieldsUsed") or ["*"], d))
    if additive:
        misses = [(pk, what, ["(new field/value: tolerant reader)"], e) for pk, what, m, e in hits + misses]
        hits = []
    seen = set()
    hits = [h for h in hits if not ((h[0].service, h[1]) in seen or seen.add((h[0].service, h[1])))]
    seen = set(h[0].service for h in hits)
    misses = [h for h in misses if not (h[0].service in seen or seen.add(h[0].service))]
    if not quiet:
        print("Impact of change to %s :: %s" % (prod.service, artefact))
        if additive:
            print("  '%s' is not in the current contract -> ADDITIVE change (kind B): no consumer impact" % field)
        if kind == "internal":
            print("  internal change — no consumer impact")
        print("  IMPACTED (%d):" % len(hits))
        for pk, what, m, _ in hits:
            print("    - %-26s %s  uses: %s" % (pk.service, what, ", ".join(m)))
        print("  NOT IMPACTED consumers of this artefact (%d):" % len(misses))
        for pk, what, m, e in misses:
            print("    - %-26s %s  (does not read %s)" % (pk.service, what, field))
    return kind, hits, misses


# ----------------------------------------------------------------------------- index
def index():
    rep = Report()
    packs = load_packs(rep)
    os.makedirs(GENERATED, exist_ok=True)
    topics, groups, templates, reasons, products, entity, prefixes, apis_used = [], [], [], [], [], [], [], []
    edges = {}
    for pk in packs.values():
        for t, meta in pk.topic_meta.items():
            topics.append({"topic": t, "owner": pk.service, "kind": meta.get("_kind"), "key": meta.get("key"),
                           "compacted": meta.get("compacted"), "tombstones": meta.get("tombstones"),
                           "partitions": meta.get("partitions"),
                           "eventTypes": ["%s v%s" % (e.get("type"), e.get("version")) for e in meta.get("eventTypes") or []]})
        for t in pk.codes.get("notificationTemplates") or []:
            templates.append(dict(t, sender=pk.service))
        for r in pk.codes.get("reasonCodes") or []:
            reasons.append(dict(r, owner=pk.service))
        for p in pk.codes.get("productCodes") or []:
            products.append({"code": p, "owner": pk.service})
        for e in pk.codes.get("entityTypes") or []:
            entity.append(dict(e, service=pk.service))
        for p in pk.codes.get("txnRefPrefixes") or []:
            prefixes.append(dict(p, owner=pk.service) if isinstance(p, dict) else {"prefix": p, "owner": pk.service})
        c = pk.consumes
        for api in c.get("apis") or []:
            edges.setdefault((pk.service, api.get("producer")), set()).add("REST")
            apis_used.append({"consumer": pk.service, "producer": api.get("producer"), "operation": api.get("operation"),
                              "pinned": api.get("pinnedContractVersion"), "fieldsUsed": api.get("fieldsUsed")})
        for k in ("events", "inboundTopics"):
            for ev in c.get(k) or []:
                prodn = ev.get("producer") or ev.get("owner")
                if k == "events":
                    edges.setdefault((pk.service, prodn), set()).add(ev.get("topic"))
                    groups.append({"groupId": ev.get("groupId"), "service": pk.service, "topic": ev.get("topic"),
                                   "eventType": ev.get("eventType"), "producer": prodn,
                                   "pinned": ev.get("pinnedContractVersion"), "fieldsUsed": ev.get("fieldsUsed")})
                else:
                    edges.setdefault((pk.service, prodn), set()).add(ev.get("topic") + " (writes)")
        for d in c.get("data") or []:
            edges.setdefault((pk.service, d.get("producer")), set()).add("data:" + str(d.get("id")))
    dump = {"topics": topics, "consumer-groups": groups, "notification-templates": templates,
            "reason-codes": reasons, "product-codes": products, "entity-types": entity,
            "txnref-prefixes": prefixes, "api-usage": apis_used}
    for name, val in dump.items():
        with open(os.path.join(GENERATED, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(val, f, indent=2, ensure_ascii=False)
            f.write("\n")
    # DEPENDENCY-INDEX.md
    L = ["# Dependency Index (GENERATED by `contracts.py index` — do not edit)", "",
         "Generated %s from %d packs. Source of truth = each pack's `contracts/contract.yaml`." % (
             _dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), len(packs)), "",
         "## 1. Packs", "", "| Service | contractVersion | Kernel | Provided ops | Produced eventTypes | Consumed ops | Consumed eventTypes |",
         "|---|---|---|---|---|---|---|"]
    for pk in packs.values():
        L.append("| %s | %s | %s | %d | %d | %d | %d |" % (
            pk.service, pk.m.get("contractVersion"), pk.m.get("kernel"), len(pk.ops),
            len([k for k, e in pk.events.items() if e["kind"] == "events"]),
            len(pk.consumes.get("apis") or []), len(pk.consumes.get("events") or [])))
    L += ["", "## 2. Who depends on whom (consumer → producer)", "", "| Consumer | Producer | Via |", "|---|---|---|"]
    for (cons, prod), via in sorted(edges.items()):
        L.append("| %s | %s | %s |" % (cons, prod, ", ".join(sorted(via))))
    L += ["", "## 3. Topics", "", "| Topic | Owner | Key | Compacted / tombstones | Event types | Consumers (group → eventType) |", "|---|---|---|---|---|---|"]
    for t in sorted(topics, key=lambda x: x["topic"]):
        cons = sorted({"%s (%s)" % (g["groupId"] or g["service"], g["eventType"]) for g in groups if g["topic"] == t["topic"]})
        writers = sorted({pk.service for pk in packs.values() for ev in pk.consumes.get("inboundTopics") or [] if ev.get("topic") == t["topic"]})
        L.append("| `%s` | %s | %s | %s / %s | %s | %s%s |" % (
            t["topic"], t["owner"], t.get("key") or "", t.get("compacted"), t.get("tombstones"),
            ", ".join(t["eventTypes"]), "<br>".join(cons) or "—", ("<br>**writers:** " + ", ".join(writers)) if writers else ""))
    L += ["", "## 4. REST usage", "", "| Producer | Operation | Consumer | Pinned | Fields used |", "|---|---|---|---|---|"]
    for a in sorted(apis_used, key=lambda x: (x["producer"] or "", x["operation"] or "", x["consumer"])):
        L.append("| %s | `%s` | %s | %s | %s |" % (a["producer"], a["operation"], a["consumer"], a["pinned"],
                                                 ", ".join("`%s`" % f for f in (a["fieldsUsed"] or []))))
    L += ["", "## 5. Generated registries", "",
          "`generated/notification-templates.json` (%d) · `generated/reason-codes.json` (%d groups) · `generated/product-codes.json` (%d) · `generated/entity-types.json` (%d) · `generated/txnref-prefixes.json` (%d) · `generated/consumer-groups.json` (%d) · `generated/topics.json` (%d)" % (
              len(templates), len(reasons), len(products), len(entity), len(prefixes), len(groups), len(topics)), ""]
    with open(os.path.join(GLOBAL, "DEPENDENCY-INDEX.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    write_system_context(packs, edges)
    print("index: %d packs, %d topics, %d groups, %d templates → DEPENDENCY-INDEX.md, SYSTEM-CONTEXT.md, generated/*.json" % (
        len(packs), len(topics), len(groups), len(templates)))


def write_system_context(packs, edges):
    path = os.path.join(GLOBAL, "SYSTEM-CONTEXT.md")
    head = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            txt = f.read()
        head = txt.split("<!-- GENERATED BELOW -->")[0]
    if not head.strip():
        head = "# System Context\n\n"
    nid = lambda s: re.sub(r"[^A-Za-z0-9]", "_", s)
    L = ["<!-- GENERATED BELOW -->", "## Generated dependency graph (from contract.yaml pins)", "", "```mermaid", "flowchart LR"]
    for pk in packs.values():
        L.append('  %s["%s<br/>v%s"]' % (nid(pk.service), pk.service, pk.m.get("contractVersion")))
    for (cons, prod), via in sorted(edges.items()):
        if prod is None:
            continue
        rest = "REST" in via
        evs = sorted(v for v in via if v != "REST")
        label = ("REST" + (" + " if evs else "") if rest else "") + (", ".join(evs) if len(evs) <= 2 else "%d topics" % len(evs))
        L.append('  %s -- "%s" --> %s' % (nid(cons), label.replace('"', "'"), nid(prod)))
    L += ["```", "", "*Arrow = consumer → producer (\"depends on\"). `(writes)` = writer of an admin-owned inbound topic.*", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write(head.rstrip() + "\n\n" + "\n".join(L))


# ----------------------------------------------------------------------------- change requests
CR_RE = re.compile(r"^CR-([A-Z0-9]+)-(\d+)$")


def svc_code(service):
    return re.sub(r"-SERVICE$", "", service.upper()).replace("-", "")


def find_cr(cr_id, packs):
    for pk in packs.values():
        p = os.path.join(pk.dir, "changes", cr_id + ".md")
        if os.path.exists(p):
            return pk, p
    sys.exit("CR %s not found in any pack's changes/ folder" % cr_id)


def cr_field(text, name):
    m = re.search(r"^\|\s*%s\s*\|\s*(.*?)\s*\|\s*$" % re.escape(name), text, re.M)
    return m.group(1) if m else ""


def set_cr_field(text, name, value):
    return re.sub(r"^(\|\s*%s\s*\|\s*)(.*?)(\s*\|\s*)$" % re.escape(name), lambda m: m.group(1) + value + m.group(3), text, count=1, flags=re.M)


def update_cr_log(cr_id, producer=None, kind=None, title=None, state=None, impacted=None):
    path = os.path.join(GLOBAL, "CR-LOG.md")
    with open(path, encoding="utf-8") as f:
        lines = f.read().rstrip("\n").split("\n")
    today = _dt.date.today().isoformat()
    for i, ln in enumerate(lines):
        if ln.startswith("| %s |" % cr_id):
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if kind: cells[2] = kind
            if title: cells[3] = title
            if state: cells[4] = state
            if impacted is not None: cells[5] = impacted
            cells[7] = today
            lines[i] = "| " + " | ".join(cells) + " |"
            break
    else:
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (cr_id, producer or "", kind or "", title or "", state or "Draft", impacted or "", today, today))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def cr_new(svc, title):
    packs = load_packs(Report())
    pk = packs.get(svc) or next((p for p in packs.values() if p.folder == svc), None)
    if not pk:
        sys.exit("unknown service %s" % svc)
    code = svc_code(pk.service)
    cdir = os.path.join(pk.dir, "changes")
    os.makedirs(cdir, exist_ok=True)
    n = 1 + max([int(m.group(2)) for f in os.listdir(cdir) for m in [CR_RE.match(f[:-3])] if f.endswith(".md") and m] or [0])
    cr_id = "CR-%s-%d" % (code, n)
    with open(os.path.join(GLOBAL, "templates", "CR-template.md"), encoding="utf-8") as f:
        t = f.read()
    t = t.replace("CR-<SVC>-<n>", cr_id).replace("<short title>", title).replace("<service>", pk.service)
    t = t.replace("YYYY-MM-DD", _dt.date.today().isoformat())
    p = os.path.join(cdir, cr_id + ".md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(t)
    update_cr_log(cr_id, producer=pk.service, title=title, state="Draft")
    print("created %s" % rel(p))


def cr_analyse(cr_id):
    packs = load_packs(Report())
    pk, p = find_cr(cr_id, packs)
    with open(p, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"## 3\. Artefacts touched\n(.*?)\n## ", text, re.S)
    arts = [re.sub(r"^\s*-\s*", "", l).strip().strip("`") for l in (m.group(1) if m else "").splitlines()
            if l.strip().startswith("-")]
    kind = cr_field(text, "Kind").strip()
    plan = ["## 5. Adoption Plan", "*(generated by `contracts.py cr analyse` on %s — re-run after changing §3)*" % _dt.date.today().isoformat(), ""]
    impacted_all = {}
    not_impacted = {}
    for a in arts:
        k, hits, misses = impact(pk.service, a, packs, quiet=True)
        for cpk, what, used, _ in hits:
            impacted_all.setdefault(cpk.service, []).append("%s — matched %s" % (what, ", ".join(used)))
        for cpk, what, used, _ in misses:
            not_impacted.setdefault(cpk.service, []).append("%s (does not read the changed field)" % what)
    folder = lambda s: packs[s].folder
    plan += ["### 5.1 Producer — %s (`services/%s/`)" % (pk.service, pk.folder), "",
             "- [ ] `contracts/provided/*` — %s" % ("; ".join("`%s`" % a for a in arts) or "internal only"),
             "- [ ] `SPEC.md` §5 (tables + examples), §3.1 edge labels, §7 rules, §11 tests as affected",
             "- [ ] `SPEC.md` §10: add **WP-%s**" % cr_id,
             "- [ ] `contracts/contract.yaml` `contractVersion` bump (%s)" % {"A": "none", "B": "MINOR", "C": "MAJOR (keep old major side by side)", "D": "MINOR (or MAJOR if breaking)", "E": "kernel"}.get(kind[:1], "per kind"),
             "- [ ] `SPEC.md` §14 changelog row", ""]
    plan += ["### 5.2 Impacted consumers (%d)" % len(impacted_all), ""]
    if not impacted_all:
        plan.append("None — no other pack reads the changed artefacts/fields." + (" ⚠ Kind C declared but zero impact: consider reclassifying as B." if kind.startswith("C") else ""))
    for s, why in sorted(impacted_all.items()):
        plan += ["- [ ] **%s** (`services/%s/`): %s" % (s, folder(s), "; ".join(why)),
                 "  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot %s`" % s,
                 "  - update `SPEC.md` §6 subsection for %s + rules/WPs/tests that use the matched fields; add WP-%s; changelog row" % (pk.service, cr_id)]
    if kind.startswith("B") and impacted_all:
        plan.append("\n⚠ Kind B declared but consumers are impacted — reclassify as C.")
    plan += ["", "### 5.3 Not impacted (%d) — do not open these packs" % len(not_impacted), ""]
    for s, why in sorted(not_impacted.items()):
        if s not in impacted_all:
            plan.append("- %s: %s" % (s, "; ".join(why)))
    baseline = {s: pack_hash(pp.dir) for s, pp in packs.items()}
    plan_packs = sorted([pk.service] + list(impacted_all))
    side = os.path.join(pk.dir, "changes", "." + cr_id + ".baseline.json")
    with open(side, "w", encoding="utf-8") as f:
        json.dump({"cr": cr_id, "analysedAt": _dt.datetime.utcnow().isoformat() + "Z", "kind": kind,
                   "planPacks": plan_packs, "baseline": baseline}, f, indent=2)
    new = re.sub(r"## 5\. Adoption Plan\n.*?(?=\n## 6\.)", "\n".join(plan) + "\n", text, flags=re.S)
    new = set_cr_field(new, "State", "Analysed")
    new = set_cr_field(new, "Baseline hash", hashlib.sha256(json.dumps(baseline, sort_keys=True).encode()).hexdigest()[:16])
    with open(p, "w", encoding="utf-8") as f:
        f.write(new)
    update_cr_log(cr_id, kind=kind, state="Analysed", impacted=", ".join(sorted(impacted_all)) or "none")
    print("%s analysed: producer %s, %d impacted consumer(s): %s" % (cr_id, pk.service, len(impacted_all), ", ".join(sorted(impacted_all)) or "none"))


def cr_verify(cr_id):
    packs = load_packs(Report())
    pk, p = find_cr(cr_id, packs)
    side = os.path.join(pk.dir, "changes", "." + cr_id + ".baseline.json")
    if not os.path.exists(side):
        sys.exit("run `cr analyse %s` first" % cr_id)
    base = load_json(side)
    changed = sorted(s for s, pp in packs.items() if pack_hash(pp.dir) != base["baseline"].get(s))
    plan = set(base["planPacks"])
    outside = [s for s in changed if s not in plan]
    untouched = [s for s in plan if s not in changed]
    print("%s verify — plan: %s" % (cr_id, ", ".join(sorted(plan))))
    print("  changed packs : %s" % (", ".join(changed) or "none"))
    rc = 0
    if outside:
        print("  ERROR packs changed OUTSIDE the Adoption Plan: %s" % ", ".join(outside))
        rc = 1
    if untouched and not base.get("kind", "").startswith("A"):
        print("  ERROR planned packs not changed yet: %s" % ", ".join(untouched))
        rc = 1
    rc |= check([*plan])
    if rc == 0:
        with open(p, encoding="utf-8") as f:
            text = f.read()
        with open(p, "w", encoding="utf-8") as f:
            f.write(set_cr_field(text, "State", "Verified"))
        update_cr_log(cr_id, state="Verified")
        print("  OK — state Verified")
    return rc


def cr_log():
    with open(os.path.join(GLOBAL, "CR-LOG.md"), encoding="utf-8") as f:
        print(f.read())


# ----------------------------------------------------------------------------- main
def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd == "check":
        return check(argv[2:] or None)
    if cmd == "snapshot" and len(argv) == 3:
        snapshot(argv[2])
        return 0
    if cmd == "index":
        index()
        return 0
    if cmd == "impact" and len(argv) == 4:
        k, hits, _ = impact(argv[2], argv[3])
        return 0
    if cmd == "cr" and len(argv) >= 3:
        sub = argv[2]
        if sub == "new" and len(argv) == 5:
            cr_new(argv[3], argv[4]); return 0
        if sub == "analyse" and len(argv) == 4:
            cr_analyse(argv[3]); return 0
        if sub == "verify" and len(argv) == 4:
            return cr_verify(argv[3])
        if sub == "log":
            cr_log(); return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
