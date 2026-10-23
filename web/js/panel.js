// The tuning drawer: built from the same schema as the desktop panel (config.py), edits the
// running universe live; presets are saved in this browser and exported as desktop-compatible JSON.
(function () {
"use strict";
const DU = window.DU, DATA = window.DU_DATA;
const $ = (id) => document.getElementById(id);

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
const tidy = (v) => Number(Number(v).toPrecision(5));
const getp = (o, path) => path.split(".").reduce((a, k) => (a == null ? a : a[k]), o);
function setp(o, path, v) { const ks = path.split("."); const last = ks.pop(); ks.reduce((a, k) => a[k], o)[last] = v; }
const hex = (c) => "#" + c.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));

function problems(p) {
  const out = [];
  p.layers.forEach((L, i) => {
    if (i && L.pulls.some((pl) => pl.enabled && pl.source === "above")) {
      const above = p.layers[i - 1];
      if (above.count * L.count > DATA.max_pairs)
        out.push(`${L.name} ← ${above.name}: ${above.count} × ${L.count} 对太多，这个力被跳过了（上层要少）`);
    }
  });
  const names = p.layers.map((l) => l.name);
  for (const n of new Set(names)) if (names.filter((x) => x === n).length > 1) out.push(`层名 ${n} 重复了`);
  return out;
}

class Panel {
  constructor(hooks) {
    this.h = hooks; this.P = null; this.timer = 0; this.nameMode = null;
    this.SCHEMA = DATA.schema; this.LAWS = DATA.laws;
    this.WHEN = new Set();
    const all = [...this.SCHEMA.preset.flatMap(([, s]) => s), ...this.SCHEMA.layer.flatMap(([, s]) => s), ...this.SCHEMA.field];
    for (const spec of all) for (const k of Object.keys(spec.when || {})) this.WHEN.add(k.replace(/^preset\./, ""));

    $("panelSel").onchange = (e) => { if (e.target.value) this.h.load(e.target.value); };
    $("pNew").onclick = () => this.h.blank();
    $("pSave").onclick = () => this.h.save();
    $("pSaveAs").onclick = () => this.askName("saveas", "");
    $("pRename").onclick = () => this.askName("rename", this.P ? this.P.title : "");
    this.twoClick($("pDelete"), "删除", () => this.h.remove());
    $("pReset").onclick = () => this.h.reset();
    $("pExport").onclick = () => this.h.exportJson();
    $("pImport").onclick = () => $("importFile").click();
    $("importFile").onchange = async (e) => {
      const f = e.target.files && e.target.files[0];
      if (f) this.h.importJson(await f.text());
      e.target.value = "";
    };
    $("nameOk").onclick = () => {
      const name = $("nameInput").value.trim();
      if (!name) return;
      if (this.nameMode === "saveas") this.h.saveAs(name);
      if (this.nameMode === "rename") this.h.rename(name);
      $("namebox").classList.remove("show");
    };
    $("nameInput").onkeydown = (e) => {
      if (e.key === "Enter") $("nameOk").click();
      if (e.key === "Escape") $("namebox").classList.remove("show");
      e.stopPropagation();
    };
  }

  isOpen() { return $("panel").classList.contains("open"); }

  /** A new preset is showing: take a fresh working copy. */
  sync(force) {
    const st = this.h.state();
    this.P = DU.toPlain(st.preset);
    this.fillPresets();
    if (this.isOpen() || force) this.render();
    this.status();
  }

  changed(rerender) {
    if (rerender) this.render();
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.h.apply(DU.clone(this.P)), 40);
  }

  askName(mode, initial) {
    this.nameMode = mode;
    $("namebox").classList.add("show");
    $("nameInput").value = initial || "";
    $("nameInput").placeholder = mode === "rename" ? "新名字" : "名字，如 我的星系";
    $("nameInput").focus(); $("nameInput").select();
  }

  twoClick(btn, label, fn) {
    let armed = 0;
    btn.onclick = () => {
      if (Date.now() - armed < 3000) { armed = 0; btn.textContent = label; fn(); return; }
      armed = Date.now(); btn.textContent = "再点一次" + label;
      setTimeout(() => { btn.textContent = label; }, 3000);
    };
  }

  fillPresets() {
    const s = $("panelSel"), st = this.h.state(), listing = this.h.listing();
    s.replaceChildren();
    const groups = {};
    for (const [key, title, group, slot] of listing) {
      if (!groups[group]) { groups[group] = el("optgroup"); groups[group].label = group; s.append(groups[group]); }
      const o = el("option", null, slot ? `${title}  (${slot})` : title); o.value = key; groups[group].append(o);
    }
    if (!st.key) { const o = el("option", null, "（未保存的新预设）"); o.value = ""; s.prepend(o); }
    s.value = st.key || "";
    $("pSave").disabled = !st.editable;
    $("pRename").disabled = !st.editable;
    $("pDelete").disabled = !st.editable;
  }

  status() {
    if (!this.P) return;
    const st = this.h.state(), box = $("pstatus");
    const counts = Object.entries(st.counts).map(([k, v]) => `${k} ${v}`).join(" · ");
    box.replaceChildren(document.createTextNode(`● ${st.fps.toFixed(0)} fps   ${counts}${st.paused ? "   已暂停" : ""}`));
    const chain = ["鼠标", ...this.P.layers.map((L) => {
      const extra = [...new Set(L.pulls.filter((p) => p.enabled && p.source !== "above").map((p) => (p.source === "mouse" ? "+鼠标" : "+中心")))];
      return L.name + (extra.length ? `(${extra.join("")})` : "");
    })];
    box.append(el("br"), el("span", "tree", "层级  " + chain.join(" → ")));
    for (const w of problems(this.P)) box.append(el("br"), el("span", "warn", "⚠ " + w));
    if (st.message) box.append(el("br"), el("span", "msg", st.message));
    $("pdesc").textContent = this.P.description || "";
  }

  visible(spec, obj) {
    if (!spec.when) return true;
    return Object.entries(spec.when).every(([k, want]) => {
      const v = k.startsWith("preset.") ? getp(this.P, k.slice(7)) : getp(obj, k);
      return want === "nonzero" ? !!v : want.includes(v);
    });
  }

  // ---------------------------------------------------------- controls
  slider(get, set, o, rerenderKey) {
    const wrap = el("div", "num");
    const range = el("input"); range.type = "range";
    const box = el("input"); box.type = "number"; box.step = o.step !== undefined ? o.step : "any";
    const isLog = o.kind === "log", isInt = o.kind === "int" || o.int;
    let lo = o.min !== undefined ? o.min : 0, hi = o.max !== undefined ? o.max : 100;
    const v0 = get();
    if (!isLog && typeof v0 === "number") {
      if (v0 > hi) hi = v0 * 1.5;
      if (v0 < lo) lo = v0 < 0 ? v0 * 1.5 : v0;
    }
    if (o.symmetric) { const m = Math.max(Math.abs(lo), Math.abs(hi)); lo = -m; hi = m; }
    const llo = isLog ? Math.log10(Math.max(o.min, 1e-9)) : 0, lhi = isLog ? Math.log10(o.max) : 0;
    const toS = (v) => (isLog ? (v <= 0 ? 0 : Math.max(1, Math.min(1000, (Math.log10(v) - llo) / (lhi - llo) * 1000))) : v);
    const fromS = (s) => (isLog ? (s <= 0 ? 0 : Math.pow(10, llo + (lhi - llo) * s / 1000)) : s);
    if (isLog) { range.min = 0; range.max = 1000; range.step = 1; }
    else { range.min = lo; range.max = hi; range.step = o.step !== undefined ? o.step : (hi - lo) / 400; }
    const show = () => {
      const v = get();
      box.value = v === null || v === undefined ? "" : v;
      range.value = v === null || v === undefined ? (isLog ? 1000 : hi) : toS(v);
    };
    show();
    if (o.nullable) box.placeholder = "∞";
    range.oninput = () => {
      let v = fromS(+range.value);
      v = isInt ? Math.round(v) : tidy(v);
      set(v); box.value = v; this.changed();
    };
    range.onchange = () => { if (rerenderKey) this.render(); };
    box.onchange = () => {
      if (box.value === "" && o.nullable) set(null);
      else if (box.value !== "") set(isInt ? Math.round(+box.value) : +box.value);
      show(); this.changed(!!rerenderKey);
    };
    box.onkeydown = (e) => e.stopPropagation();
    wrap.append(range, box);
    return wrap;
  }

  control(spec, obj) {
    const get = () => getp(obj, spec.key), set = (v) => setp(obj, spec.key, v);
    const rr = this.WHEN.has(spec.key);
    switch (spec.kind) {
      case "text": {
        const t = el("input"); t.type = "text"; t.value = get() !== undefined && get() !== null ? get() : "";
        t.onchange = () => { set(t.value.trim()); this.changed(true); };
        t.onkeydown = (e) => e.stopPropagation();
        return t;
      }
      case "bool": {
        const lab = el("label", "inline"); const c = el("input"); c.type = "checkbox"; c.checked = !!get();
        c.onchange = () => { set(c.checked); this.changed(true); };
        lab.append(c); return lab;
      }
      case "sel": {
        const s = el("select");
        for (const [v, t] of spec.options) { const o = el("option", null, t); o.value = v; s.appendChild(o); }
        s.value = get();
        s.onchange = () => { set(s.value); this.changed(true); };
        return s;
      }
      case "color": {
        const c = el("input"); c.type = "color"; c.value = hex(get() || [255, 255, 255]);
        c.oninput = () => { set(rgb(c.value)); this.changed(); };
        return c;
      }
      case "vec2": {
        const v = el("div", "vec");
        [0, 1].forEach((i) => {
          const s = this.slider(() => get()[i], (x) => { get()[i] = x; }, spec);
          s.prepend(el("span", null, (spec.labels || ["x", "y"])[i]));
          v.append(s);
        });
        return v;
      }
      default: {
        if (spec.nullable_label) {                         // e.g. layer friction: null = use the global one
          const box = el("div");
          const lab = el("label", "inline"); const c = el("input"); c.type = "checkbox"; c.checked = get() === null;
          c.onchange = () => { set(c.checked ? null : (getp(this.P, spec.key) !== undefined ? getp(this.P, spec.key) : 0.0005)); this.changed(true); };
          lab.append(c, document.createTextNode(" " + spec.nullable_label));
          box.append(lab);
          if (get() !== null) box.append(this.slider(get, set, spec, rr));
          return box;
        }
        return this.slider(get, set, spec, rr);
      }
    }
  }

  rows(target, specs, obj) {
    for (const spec of specs) {
      if (!this.visible(spec, obj)) continue;
      const r = el("div", "row");
      r.append(el("label", null, spec.label), this.control(spec, obj));
      r.title = spec.key;
      target.append(r);
      if (spec.hint) target.append(el("div", "hint", spec.hint));
    }
  }

  button(text, fn, cls = "small") {
    const b = el("button", cls, text);
    b.onclick = (e) => { e.preventDefault(); e.stopPropagation(); fn(); };
    return b;
  }

  card(title, tag, open, key, build, tools) {
    const d = el("details"); d.open = open; d.dataset.key = key;
    const s = el("summary"); s.append(el("span", null, title));
    if (tag) s.append(el("span", "tag", tag));
    s.append(el("span", "spacer"));
    for (const t of tools || []) s.append(t);
    const body = el("div", "body"); build(body);
    d.append(s, body);
    return d;
  }

  // ---------------------------------------------------------- layers and forces
  sourceName(i, src) {
    if (src === "mouse") return "鼠标";
    if (src === "center") return "屏幕中心";
    return `上一层（${i === 0 ? "鼠标" : this.P.layers[i - 1].name}）`;
  }

  pullBox(L, i, p, j) {
    const box = el("div", "pull" + (p.enabled ? "" : " off"));
    const head = el("div", "pullhead");
    const en = el("input"); en.type = "checkbox"; en.checked = p.enabled;
    en.onchange = () => { p.enabled = en.checked; this.changed(true); };
    const src = el("select");
    for (const v of ["above", "mouse", "center"]) { const o = el("option", null, this.sourceName(i, v)); o.value = v; src.appendChild(o); }
    src.value = p.source; src.onchange = () => { p.source = src.value; this.changed(true); };
    head.append(en, document.createTextNode("来自"), src, el("span", "spacer"),
                this.button("删除", () => { L.pulls.splice(j, 1); this.changed(true); }));
    box.append(head);
    this.rows(box, this.SCHEMA.field, p.field);
    const hint = this.LAWS[p.field.law];
    if (hint) box.insertBefore(el("div", "hint", hint), box.children[2] || null);
    if (p.source === "above" && i > 0 && this.P.layers[i - 1].count * L.count > DATA.max_pairs)
      box.append(el("div", "hint", `⚠ 上一层 ${this.P.layers[i - 1].count} 个 × 本层 ${L.count} 个太多，这个力会被跳过`));
    return box;
  }

  newField(strength, minDist) {
    return Object.assign(DU.clone(DATA.defaults.field), { law: "classic", strength, min_dist: minDist, max_dist: null });
  }

  layerCard(L, i) {
    const P = this.P, n = P.layers.length;
    const tools = [
      this.button("↑", () => { if (i > 0) { [P.layers[i - 1], P.layers[i]] = [P.layers[i], P.layers[i - 1]]; this.changed(true); } }),
      this.button("↓", () => { if (i < n - 1) { [P.layers[i + 1], P.layers[i]] = [P.layers[i], P.layers[i + 1]]; this.changed(true); } }),
      this.button("复制", () => {
        const c = DU.clone(L); c.name = this.nextName(L.name.replace(/\d+$/, ""));
        P.layers.splice(i + 1, 0, c); this.changed(true);
      }),
      this.button("删除", () => { P.layers.splice(i, 1); this.changed(true); }),
    ];
    const st = this.h.state();
    const count = st.counts && st.counts[L.name] !== undefined ? st.counts[L.name] : L.count;
    const above = i === 0 ? "鼠标" : P.layers[i - 1].name;
    return this.card(`第 ${i + 1} 层 · ${L.name}`, `${count} 个 · 受 ${above} 吸引`, true, "layer" + i, (b) => {
      this.SCHEMA.layer.forEach(([title, specs], k) => {
        if (k === 0) { this.rows(b, specs, L); return; }
        b.append(this.card(title, null, title === "运动" || title === "外观", `layer${i}-${title}`, (x) => this.rows(x, specs, L)));
        if (title === "运动") {
          b.append(this.card("受力（只来自上一层；鼠标和屏幕中心是全局的）", `${L.pulls.length} 个`, true, `layer${i}-pulls`, (x) => {
            L.pulls.forEach((p, j) => x.append(this.pullBox(L, i, p, j)));
            x.append(this.button("+ 添加一个力", () => {
              L.pulls.push({ source: "above", enabled: true, field: this.newField(20, 5) });
              this.changed(true);
            }, ""));
          }));
        }
      });
    }, tools);
  }

  nextName(base) {
    base = base || "layer";
    let k = 1;
    while (this.P.layers.some((x) => x.name === `${base}${k}`)) k++;
    return `${base}${k}`;
  }

  newLayer(kind) {
    const P = this.P, star = kind === "star";
    const L = Object.assign(DU.clone(DATA.defaults.layer), {
      name: this.nextName(star ? "star" : "dust"), count: star ? 3 : 15000, look: star ? "dot" : "pixel",
      dot: 8, color_mode: star ? "fixed" : "palette", velocity: "random",
      pulls: [{ source: "above", enabled: true, field: this.newField(star ? 30 : 15, star ? 10 : 3) }],
    });
    const last = P.layers[P.layers.length - 1];
    if (star && last && last.look === "pixel") P.layers.splice(P.layers.length - 1, 0, L);
    else P.layers.push(L);
    const k = P.layers.indexOf(L);
    if (k > 0 && P.layers[k - 1].count * L.count > DATA.max_pairs) L.pulls[0].source = "mouse";
    this.changed(true);
  }

  render() {
    if (!this.P) return;
    const form = $("form"), open = {};
    for (const d of form.querySelectorAll("details")) open[d.dataset.key] = d.open;
    const y = form.scrollTop;
    form.replaceChildren();
    this.SCHEMA.preset.forEach(([title, specs], k) =>
      form.append(this.card(title, k === 0 ? this.P.title : null, false, "p-" + title, (b) => this.rows(b, specs, this.P))));
    form.append(el("div", "sub", "层（从上到下；每层只受上一层吸引）"));
    this.P.layers.forEach((L, i) => form.append(this.layerCard(L, i)));
    const adders = el("div", "adders");
    adders.append(this.button("+ 星层（圆点，少量，当吸引源）", () => this.newLayer("star"), ""),
                  this.button("+ 尘层（像素，大量）", () => this.newLayer("dust"), ""));
    form.append(adders);
    for (const d of form.querySelectorAll("details")) if (open[d.dataset.key] !== undefined) d.open = open[d.dataset.key];
    form.scrollTop = y;
    this.status();
  }
}

DU.Panel = Panel;
})();
