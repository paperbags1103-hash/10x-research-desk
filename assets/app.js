/* ==========================================================================
   10X Research Desk — data-driven static SPA (no build step)
   Data contract: data/*.json  ·  Renderer: this file only
   ========================================================================== */
(function () {
  "use strict";

  var FILES = ["meta", "briefing", "memos", "ledger", "playbook", "scorecard", "frontier"];
  var D = {};
  var app = document.getElementById("app");
  var state = {
    view: "overview",
    memoIdx: 0,
    alloc: "desk",
    filter: "all",
    frontierIdx: 0
  };

  /* ---------------------------------------------------------------- utils */

  function md(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\n/g, "<br>");
  }

  // md() escapes by default; this variant allows the small inline tags the
  // data files are allowed to use (<b>, <br>, <small>…).
  function rich(s) {
    if (s === null || s === undefined) return "";
    return String(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>");
  }

  function fmtDate(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    try {
      return new Intl.DateTimeFormat("en-GB", {
        day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
        timeZone: "Asia/Seoul", hour12: false
      }).format(d).replace(",", "") + " KST";
    } catch (e) {
      return iso;
    }
  }

  function esc(s) {
    return String(s === undefined || s === null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // Text colour that stays readable on a given segment background.
  function segInk(hex) {
    var h = String(hex || "#333").replace("#", "");
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    var r = parseInt(h.substr(0, 2), 16) || 0,
      g = parseInt(h.substr(2, 2), 16) || 0,
      b = parseInt(h.substr(4, 2), 16) || 0;
    return (0.299 * r + 0.587 * g + 0.114 * b) > 150 ? "#0a0b0d" : "#eef1ee";
  }

  /* --------------------------------------------------------------- blocks */

  function blockTable(b) {
    var align = b.align || [];
    var head = b.columns.map(function (c, i) {
      return '<th class="' + (align[i] === "r" ? "num" : "") + '">' + esc(c) + "</th>";
    }).join("");
    var body = b.rows.map(function (r) {
      var cells = r.map(function (c, i) {
        var cls = [];
        if (align[i] === "r") cls.push("num");
        var tag = (i === 0 && b.rowhead !== false) ? "th" : "td";
        return "<" + tag + ' class="' + cls.join(" ") + '">' + rich(c) + "</" + tag + ">";
      }).join("");
      return "<tr>" + cells + "</tr>";
    }).join("");
    return '<div class="tw"><table><thead><tr>' + head + "</tr></thead><tbody>" + body + "</tbody></table>" +
      (b.note ? '<div class="t-note">' + rich(b.note) + "</div>" : "") + "</div>";
  }

  function blockKv(b) {
    var rows = b.rows.map(function (r) {
      return '<div class="kpi"><span class="k">' + rich(r[0]) + '</span><span class="v">' + rich(r[1]) +
        (r[2] ? "<small>" + rich(r[2]) + "</small>" : "") + "</span></div>";
    }).join("");
    return '<div class="kpi-list">' + rows + "</div>";
  }

  function blockList(b) {
    var tag = b.ordered ? "ol" : "ul";
    var cls = "clean" + (b.ordered ? "" : "") + (b.check ? " check" : "");
    var items = b.items.map(function (it) { return "<li>" + rich(it) + "</li>"; }).join("");
    return "<" + tag + ' class="' + cls + '">' + items + "</" + tag + ">";
  }

  function blockCards(b) {
    var cls = "grid " + (b.columns === 2 ? "g-2" : b.columns === 4 ? "g-4" : "g-3");
    var items = b.items.map(function (c) {
      return '<div class="watch">' +
        (c.tag ? '<span class="tag ' + (c.tone || "") + '">' + rich(c.tag) + "</span>" : "") +
        (c.title ? "<h4>" + rich(c.title) + "</h4>" : "") +
        (c.body ? "<p>" + rich(c.body) + "</p>" : "") +
        (c.foot ? '<span class="foot">' + rich(c.foot) + "</span>" : "") +
        "</div>";
    }).join("");
    return '<div class="' + cls + '">' + items + "</div>";
  }

  function blockCallout(b) {
    return '<div class="callout ' + (b.tone || "") + '">' +
      (b.title ? '<span class="ct">' + rich(b.title) + "</span>" : "") +
      rich(b.body) + "</div>";
  }

  function blockProse(b) {
    return '<div class="prose">' + b.paragraphs.map(function (p) { return "<p>" + rich(p) + "</p>"; }).join("") + "</div>";
  }

  function renderBlock(b) {
    switch (b.type) {
      case "table": return blockTable(b);
      case "kv": return blockKv(b);
      case "list": return blockList(b);
      case "cards": return blockCards(b);
      case "callout": return blockCallout(b);
      case "prose": return blockProse(b);
      case "raw": return b.html || "";
      default: return "";
    }
  }

  function sectionHead(num, title, aside) {
    return '<div class="sec-head"><span class="num">' + esc(num) + "</span><h2>" + esc(title) + "</h2>" +
      (aside ? '<span class="aside">' + esc(aside) + "</span>" : "") + "</div>";
  }

  function blocksToSections(blocks) {
    return blocks.map(function (b) {
      if (b.type === "section") {
        var inner = (b.blocks || []).map(renderBlock).join("");
        return '<section class="sec">' + sectionHead(b.num || "", b.title || "", b.aside) +
          '<div class="stack">' + inner + "</div></section>";
      }
      return renderBlock(b);
    }).join("");
  }

  /* -------------------------------------------------------------- overview */

  function viewOverview() {
    var b = D.briefing, m = D.meta;
    var idx = b.index || {};

    var stats = (b.stats || []).map(function (s) {
      return '<div class="stat ' + (s.tone || "") + '"><span class="k">' + esc(s.k) + "</span>" +
        '<span class="v">' + rich(s.v) + "</span>" + (s.n ? '<span class="n">' + rich(s.n) + "</span>" : "") + "</div>";
    }).join("");

    var pct = Math.max(2, Math.min(100, (idx.target / idx.scale) * 100));
    var idxCard = '<div class="card index-card">' +
      '<div class="index-top">' +
      '<div><span class="k mono" style="font-size:10px;letter-spacing:.16em;color:var(--ink-3)">' + esc(idx.label) + "</span>" +
      '<div class="index-big">' + esc(idx.base) + '<span>→</span>' + esc(idx.target) + "</div></div>" +
      '<div class="index-cap">' + rich(idx.caption) + "</div></div>" +
      '<div class="bar-track"><div class="bar-fill" style="width:' + pct.toFixed(1) + '%"></div></div>' +
      '<div class="ticks">' + (idx.ticks || []).map(function (t) { return "<span>" + esc(t) + "</span>"; }).join("") + "</div>" +
      '<div class="bar-legend">' + (idx.legend || []).map(function (l) {
        return "<span><i style=\"background:" + esc(l.color) + "\"></i>" + rich(l.text) + "</span>";
      }).join("") + "</div></div>";

    // allocation
    var allocSet = (b.allocation && b.allocation[state.alloc]) || { rows: [] };
    var total = allocSet.rows.reduce(function (a, r) { return a + (r.weight || 0); }, 0) || 1;
    var segs = allocSet.rows.map(function (r) {
      var w = (r.weight / total) * 100;
      return '<div class="alloc-seg" style="width:' + w.toFixed(2) + "%;background:" + esc(r.color) + ";color:" + segInk(r.color) + '" title="' + esc(r.name) + " " + r.weight + '%">' +
        (w > 11 ? r.weight + "%" : "") + "</div>";
    }).join("");
    var rows = allocSet.rows.map(function (r) {
      return '<div class="alloc-row"><span class="sw" style="background:' + esc(r.color) + '"></span>' +
        '<span class="nm">' + rich(r.name) + (r.note ? "<small>" + rich(r.note) + "</small>" : "") + "</span>" +
        '<span class="wt">' + r.weight + "%</span></div>";
    }).join("");
    var allocTabs = Object.keys(b.allocation || {}).map(function (key) {
      var a = b.allocation[key];
      return '<button type="button" data-act="alloc" data-val="' + esc(key) + '" aria-pressed="' +
        (state.alloc === key) + '">' + esc(a.label) + "</button>";
    }).join("");

    var allocCard = '<div class="card">' +
      '<div class="row" style="justify-content:space-between;margin-bottom:14px">' +
      '<div class="seg-tabs" role="group" aria-label="배분안">' + allocTabs + "</div>" +
      '<span class="mono tiny muted">' + esc(allocSet.kind || "") + "</span></div>" +
      '<div class="alloc-bar">' + segs + "</div>" +
      '<div class="alloc-rows">' + rows + "</div>" +
      (allocSet.note ? '<p class="tiny muted" style="margin:14px 0 0">' + rich(allocSet.note) + "</p>" : "") +
      "</div>";

    var watch = (b.watch || []).map(function (w) {
      return '<div class="watch"><span class="tag ' + (w.tone || "") + '">' + esc(w.tag) + "</span>" +
        "<h4>" + rich(w.title) + "</h4><p>" + rich(w.body) + "</p>" +
        '<span class="foot">' + rich(w.foot) + "</span></div>";
    }).join("");

    var tape = b.tape ? blockTable({
      columns: ["지표", "값", "변화", "기준"],
      rows: b.tape.rows,
      align: ["l", "r", "r", "l"],
      note: b.tape.note
    }) : "";

    var notes = (b.notes || []).map(function (n, i) {
      return '<div class="callout ' + (n.tone || "quiet") + '">' +
        (n.title ? '<span class="ct">' + rich(n.title) + "</span>" : "") + rich(n.body) + "</div>";
    }).join("");

    return '<div class="view">' +
      '<p class="eyebrow">' + esc(b.eyebrow) + "</p>" +
      '<h1 class="display">' + b.headline + "</h1>" +
      '<p class="lede">' + rich(b.lede) + "</p>" +
      '<section class="sec"><div class="stats">' + stats + "</div></section>" +
      '<section class="sec">' + idxCard + "</section>" +
      '<section class="sec">' + sectionHead("01", "배분 구조", "Allocation · weight only") +
      '<div class="stack">' + allocCard + "</div></section>" +
      '<section class="sec">' + sectionHead("02", "핵심 추적 변수", "Watch · " + (b.watch || []).length + " items") +
      '<div class="grid g-2">' + watch + "</div></section>" +
      '<section class="sec">' + sectionHead("03", "거시 테이프", b.tape ? b.tape.asof : "") + tape + "</section>" +
      (notes ? '<section class="sec">' + sectionHead("04", "데스크 노트", "Notes") + '<div class="stack">' + notes + "</div></section>" : "") +
      "</div>";
  }

  /* -------------------------------------------------------------- deepdive */

  function viewDeepDive() {
    var memos = D.memos.memos || [];
    if (!memos.length) return '<div class="view"><p class="muted">등록된 메모가 없다.</p></div>';
    var idx = Math.min(state.memoIdx, memos.length - 1);
    var m = memos[idx];

    var switcher = memos.length > 1 ? '<div class="memo-switch">' + memos.map(function (x, i) {
      return '<button type="button" data-act="memo" data-val="' + i + '" aria-pressed="' + (i === idx) + '">' +
        esc(x.id) + " · " + esc(x.ticker) + "</button>";
    }).join("") + "</div>" : "";

    var stats = (m.stats || []).map(function (s) {
      return '<div class="stat ' + (s.tone || "") + '"><span class="k">' + esc(s.label) + "</span>" +
        '<span class="v">' + rich(s.value) + "</span>" + (s.note ? '<span class="n">' + rich(s.note) + "</span>" : "") + "</div>";
    }).join("");

    var maxScn = Math.max.apply(null, (m.scenarios || []).map(function (s) { return s.multiple; }).concat([1]));
    var scn = (m.scenarios || []).map(function (s) {
      var w = Math.max(4, (s.multiple / maxScn) * 100);
      return '<div class="scn-row"><span class="name">' + esc(s.name) + "</span>" +
        '<div class="scn-track"><div class="scn-fill ' + esc(s.tone || "") + '" style="width:' + w.toFixed(1) + '%"></div></div>' +
        '<span class="val">' + s.multiple.toFixed(2) + "x<small>" + (s.prob !== undefined ? "P " + s.prob + "%" : "") + "</small></span></div>";
    }).join("");

    var scnCard = '<div class="card"><div class="row" style="justify-content:space-between;margin-bottom:16px">' +
      '<span class="mono" style="font-size:10px;letter-spacing:.16em;color:var(--ink-3)">5Y TERMINAL MULTIPLE / ENTRY ' + (m.currency === 'KRW' ? '' : '$') + esc(m.entryPrice || "") + "</span>" +
      '<span class="tiny muted">확률가중 ' + rich(m.weightedMultiple || "—") + "</span></div>" +
      '<div class="scn">' + scn + "</div>" +
      (m.scenarioNote ? '<p class="scn-note">' + rich(m.scenarioNote) + "</p>" : "") + "</div>";

    var inval = (m.invalidation || []).length ? '<section class="sec">' +
      sectionHead("INV", "펀더멘털 무효화 기준", "Invalidation · not price stops") +
      '<div class="inval">' + m.invalidation.map(function (v) {
        return '<div class="inval-row"><span class="n">' + esc(v.n) + '</span><span class="c">' + rich(v.condition) + "</span>" +
          '<span class="a">' + rich(v.action) + "</span></div>";
      }).join("") + "</div>" +
      (m.invalidationNote ? '<p class="tiny muted" style="margin-top:12px">' + rich(m.invalidationNote) + "</p>" : "") +
      "</section>" : "";

    var entry = m.entryPlan ? '<section class="sec">' +
      sectionHead("ENTRY", "실행 가이드", m.entryPlan.aside || "Tranche · % of sleeve") +
      '<div class="ladder">' + (m.entryPlan.stages || []).map(function (s, i) {
        return '<div class="rung ' + (i === 0 ? "hot" : "") + '"><span class="st">' + esc(s.stage) + "</span>" +
          '<span class="wt">' + esc(s.weight) + "<small>%</small></span>" +
          '<span class="px">' + rich(s.price) + "</span>" +
          '<span class="tm">' + rich(s.timing) + "</span>" +
          '<span class="bs">' + rich(s.basis) + "</span></div>";
      }).join("") + "</div>" +
      (m.entryPlan.note ? '<p class="tiny muted" style="margin-top:12px">' + rich(m.entryPlan.note) + "</p>" : "") +
      (m.entryPlan.warning ? '<div class="callout warn" style="margin-top:12px"><span class="ct">하지 말 것</span>' + rich(m.entryPlan.warning) + "</div>" : "") +
      "</section>" : "";

    var catalysts = (m.catalysts || []).length ? '<section class="sec">' +
      sectionHead("CAT", "촉매 캘린더", "Next 12 months") +
      '<div class="tl">' + m.catalysts.map(function (c) {
        return '<div class="tl-item ' + (c.now ? "now" : "") + '"><span class="d">' + esc(c.date) + "</span>" +
          '<div class="t">' + rich(c.event) + "</div>" + (c.note ? '<div class="x">' + rich(c.note) + "</div>" : "") + "</div>";
      }).join("") + "</div></section>" : "";

    var monitor = (m.monitoring || []).length ? '<section class="sec">' +
      sectionHead("CHK", "분기 모니터링 대시보드", "Quarterly checklist") +
      blockList({ items: m.monitoring, check: true }) + "</section>" : "";

    var gaps = (m.gaps || []).length ? '<section class="sec">' +
      sectionHead("GAP", "데이터 공백 · 미확인", "Honest unknowns") +
      '<div class="callout quiet">' + blockList({ ordered: true, items: m.gaps }) + "</div></section>" : "";

    var sources = (m.sources || []).length ? '<section class="sec">' +
      sectionHead("SRC", "출처", "Primary sources first") +
      m.sources.map(function (g) {
        return '<details class="src-group"><summary>' + esc(g.group) + "</summary><div class=\"src-list\">" +
          g.items.map(function (it) {
            if (it.url) {
              return '<a href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer">' + esc(it.label) + "</a>";
            }
            return '<span class="plain">' + esc(it.label) + "</span>";
          }).join("") + "</div></details>";
      }).join("") + "</section>" : "";

    return '<div class="view">' + switcher +
      '<header class="memo-head">' +
      '<div class="memo-tickerline">' +
      '<span class="ticker-chip">' + esc(m.ticker) + "</span>" +
      '<span class="ticker-chip ghost">' + esc(m.exchange) + "</span>" +
      '<span class="pill active dot">' + esc(m.status) + "</span>" +
      '<span class="mono tiny muted" style="margin-left:auto">' + esc(m.date) + "</span>" +
      "</div>" +
      '<p class="eyebrow">' + esc(m.kicker) + "</p>" +
      '<h1 class="display" style="font-size:clamp(1.9rem,5.4vw,3rem)">' + rich(m.title) + "</h1>" +
      '<p class="lede">' + rich(m.lede) + "</p>" +
      "</header>" +
      '<section class="sec"><div class="stats">' + stats + "</div></section>" +
      '<section class="sec">' + sectionHead("SCN", "5년 역산 시나리오", "Base is not a headline") + scnCard + "</section>" +
      blocksToSections(m.blocks || []) +
      inval + entry + catalysts + monitor + gaps + sources +
      "</div>";
  }

  /* -------------------------------------------------------------- frontier */

  function viewFrontier() {
    var R = (D.frontier && D.frontier.reports) || [];
    if (!R.length) return '<div class="view"><p class="muted">등록된 프론티어 리포트가 없다.</p></div>';
    var idx = Math.min(state.frontierIdx, R.length - 1);
    var r = R[idx];

    var switcher = R.length > 1 ? '<div class="memo-switch">' + R.map(function (x, i) {
      return '<button type="button" data-act="frontier" data-val="' + i + '" aria-pressed="' + (i === idx) + '">' +
        esc(x.id) + " · " + esc(x.domain) + "</button>";
    }).join("") + "</div>" : "";

    var stats = (r.stats || []).map(function (s) {
      return '<div class="stat ' + (s.tone || "") + '"><span class="k">' + esc(s.label) + "</span>" +
        '<span class="v">' + rich(s.value) + "</span>" + (s.note ? '<span class="n">' + rich(s.note) + "</span>" : "") + "</div>";
    }).join("");

    var grades = (r.grades || []).map(function (g) {
      var w = Math.max(4, Math.min(100, g.pct || 0));
      return '<div class="scn-row"><span class="name">' + esc(g.label) + "</span>" +
        '<div class="scn-track"><div class="scn-fill ' + esc(g.tone || "base") + '" style="width:' + w.toFixed(1) + '%"></div></div>' +
        '<span class="val">' + esc(g.grade) + (g.cap ? "<small>" + esc(g.cap) + "</small>" : "") + "</span></div>";
    }).join("");

    var gradeCard = grades ? '<div class="card"><div class="row" style="justify-content:space-between;margin-bottom:16px">' +
      '<span class="mono" style="font-size:10px;letter-spacing:.16em;color:var(--ink-3)">SCIENCE VS INDUSTRY / GRADE</span>' +
      '<span class="tiny muted">' + rich(r.status || "") + "</span></div>" +
      '<div class="scn">' + grades + "</div>" +
      (r.gradeNote ? '<p class="scn-note">' + rich(r.gradeNote) + "</p>" : "") + "</div>" : "";

    var thesis = (r.thesis || []).length ? '<section class="sec">' +
      sectionHead("00", "3줄 결론", "TL;DR") +
      '<div class="callout"><span class="ct">Read this first</span>' +
      blockList({ ordered: true, items: r.thesis }) + "</div></section>" : "";

    var inval = (r.invalidation || []).length ? '<section class="sec">' +
      sectionHead("INV", "무효화 조건", "Explicit · 2 of 4 kills it") +
      '<div class="inval">' + r.invalidation.map(function (v) {
        return '<div class="inval-row"><span class="n">' + esc(v.n) + '</span><span class="c">' + rich(v.condition) + "</span>" +
          '<span class="a">' + rich(v.action) + "</span></div>";
      }).join("") + "</div>" +
      (r.invalidationNote ? '<p class="tiny muted" style="margin-top:12px">' + rich(r.invalidationNote) + "</p>" : "") +
      "</section>" : "";

    var limits = (r.limits || []).length ? '<section class="sec">' +
      sectionHead("LIM", "한계와 오독 방지", "Honest unknowns") +
      '<div class="callout quiet">' + blockList({ ordered: true, items: r.limits }) + "</div></section>" : "";

    var sources = (r.sources || []).length ? '<section class="sec">' +
      sectionHead("SRC", "원천 목록", "Primary sources first") +
      r.sources.map(function (g) {
        return '<details class="src-group"><summary>' + esc(g.group) + '</summary><div class="src-list">' +
          g.items.map(function (it) {
            if (it.url) {
              return '<a href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer">' + esc(it.label) + "</a>";
            }
            return '<span class="plain">' + esc(it.label) + "</span>";
          }).join("") + "</div></details>";
      }).join("") + "</section>" : "";

    return '<div class="view">' + switcher +
      '<header class="memo-head">' +
      '<div class="memo-tickerline">' +
      '<span class="ticker-chip">FL-' + esc(r.id) + "</span>" +
      '<span class="ticker-chip ghost">' + esc(r.domain) + "</span>" +
      '<span class="pill active dot">' + esc(r.badge || "1차 원천") + "</span>" +
      '<span class="mono tiny muted" style="margin-left:auto">' + esc(r.date) + "</span>" +
      "</div>" +
      '<p class="eyebrow">' + esc(r.kicker) + "</p>" +
      '<h1 class="display" style="font-size:clamp(1.9rem,5.4vw,3rem)">' + rich(r.title) + "</h1>" +
      '<p class="lede">' + rich(r.lede) + "</p>" +
      "</header>" +
      '<section class="sec"><div class="stats">' + stats + "</div></section>" +
      thesis +
      (gradeCard ? '<section class="sec">' + sectionHead("GRADE", "판정 등급", "Chemistry ≠ Scale") + gradeCard + "</section>" : "") +
      blocksToSections(r.blocks || []) +
      inval + limits + sources +
      (r.footnote ? '<p class="tiny muted" style="margin-top:18px">' + rich(r.footnote) + "</p>" : "") +
      "</div>";
  }

  /* ---------------------------------------------------------------- ledger */

  var STATUS_LABELS = { wait: "진입 대기", candidate: "후보", drop: "탈락", active: "보유", watch: "관찰", closed: "종료" };
  var STATUS_ORDER = ["active", "wait", "candidate", "watch", "drop", "closed"];

  function viewLedger() {
    var L = D.ledger || { items: [] };
    var items = L.items || [];
    var present = STATUS_ORDER.filter(function (k) {
      return items.some(function (i) { return i.statusKey === k; });
    });
    if (state.filter !== "all" && present.indexOf(state.filter) === -1) state.filter = "all";
    var shown = state.filter === "all" ? items : items.filter(function (i) { return i.statusKey === state.filter; });

    var chips = ['<button type="button" class="chip" data-act="filter" data-val="all" aria-pressed="' +
      (state.filter === "all") + '">전체 <span class="mono" style="opacity:.6">' + items.length + "</span></button>"]
      .concat(present.map(function (k) {
        var n = items.filter(function (i) { return i.statusKey === k; }).length;
        return '<button type="button" class="chip" data-act="filter" data-val="' + k + '" aria-pressed="' +
          (state.filter === k) + '">' + esc(STATUS_LABELS[k] || k) + ' <span class="mono" style="opacity:.6">' + n + "</span></button>";
      })).join("");

    var cards = shown.map(function (i) {
      var fields = [
        { k: "진입 기준가", v: '<span class="price">' + esc(i.entryPrice) + "</span>", wide: false },
        { k: "구분", v: rich(i.bucket), wide: false },
        { k: "진입 계획", v: rich(i.entryPlan), wide: true },
        { k: "핵심 가설", v: rich(i.thesis), wide: true }
      ];
      var fieldHtml = fields.map(function (f) {
        return '<div class="idea-field ' + (f.wide ? "wide" : "") + '"><span class="k">' + f.k + "</span>" +
          '<div class="v">' + f.v + "</div></div>";
      }).join("");

      return '<article class="idea">' +
        '<div class="idea-top"><span class="idea-id">#' + esc(i.id) + "</span>" +
        '<span class="idea-name">' + rich(i.name) + (i.ticker ? "<small>" + esc(i.ticker) + " · " + esc(i.exchange) + "</small>" : "") + "</span>" +
        '<span class="pill ' + esc(i.statusKey) + ' dot">' + esc(i.status) + "</span></div>" +
        '<div class="idea-grid">' + fieldHtml + "</div>" +
        '<details class="more"><summary>무효화 기준 · 메모</summary><div class="v tiny" style="margin-top:10px;color:var(--ink-2);line-height:1.7">' +
        rich(i.invalidation) + (i.memo ? '<div style="margin-top:8px;color:var(--ink-4)">' + rich(i.memo) + "</div>" : "") +
        "</div></details></article>";
    }).join("");

    return '<div class="view">' +
      '<p class="eyebrow">Idea Ledger · ' + esc(L.updatedLabel || "") + "</p>" +
      '<h1 class="display" style="font-size:clamp(1.8rem,5vw,2.7rem)">아이디어는<br>기록되고 <em>반증된다</em></h1>' +
      '<p class="lede">모든 후보는 제시 시점의 가격·가설·무효화 기준으로 장부에 남는다. 상태가 바뀌는 근거도 함께 남기 때문에, 나중에 “그때 왜 그렇게 봤는지”를 되짚을 수 있다.</p>' +
      '<div class="ledger-tools">' + chips + '<span class="ledger-count">' + shown.length + " / " + items.length + " SHOWN</span></div>" +
      '<div class="stack">' + (cards || '<p class="muted tiny">해당 상태의 아이디어가 없다.</p>') + "</div>" +
      (L.footnote ? '<p class="tiny muted" style="margin-top:18px">' + rich(L.footnote) + "</p>" : "") +
      "</div>";
  }

  /* ---------------------------------------------------------------- system */

  function viewSystem() {
    var S = D.scorecard, P = D.playbook;
    var total = S.total || 0;
    var pct = Math.max(0, Math.min(100, total));

    var crit = (S.criteria || []).map(function (c) {
      var w = (c.score / c.max) * 100;
      return '<div class="crit-row"><div class="top"><span class="nm">' + esc(c.name) + "</span>" +
        '<span class="sc"><b>' + c.score + "</b> / " + c.max + "</span></div>" +
        '<div class="crit-track"><div class="crit-fill ' + (c.score === 0 ? "dim" : "") + '" style="width:' + w.toFixed(0) + '%"></div></div>' +
        (c.note ? '<div class="note">' + rich(c.note) + "</div>" : "") + "</div>";
    }).join("");

    var logs = (S.history || []).map(function (h, i) {
      return '<div class="logitem ' + (i === 0 ? "latest" : "") + '">' +
        '<span class="when">' + esc(h.date) + (h.score !== undefined ? " · " + h.score + (h.max ? " / " + h.max : " pts") : "") + "</span>" +
        "<h4>" + rich(h.title) + "</h4>" +
        (h.body || []).map(function (p) { return "<p>" + rich(p) + "</p>"; }).join("") +
        ((h.actions && h.actions.length) ? '<div style="margin-top:8px">' + blockList({ ordered: true, items: h.actions }) + "</div>" : "") +
        "</div>";
    }).join("");

    var rules = (P.rules || []).map(function (r, i) {
      return '<div class="rule"><div class="rule-head"><span class="n">R' + (i + 1) + "</span><h4>" + rich(r.title) + "</h4></div>" +
        '<ul>' + r.items.map(function (it) { return "<li>" + rich(it) + "</li>"; }).join("") + "</ul></div>";
    }).join("");

    var changelog = (P.changelog || []).map(function (c) {
      return '<div class="cl-item"><span class="v">v' + esc(c.version) + "</span><span>" + rich(c.note) + "</span></div>";
    }).join("");

    var principles = (S.principles || []).map(function (p) { return "<li>" + rich(p) + "</li>"; }).join("");

    return '<div class="view">' +
      '<p class="eyebrow">Self-Eval &amp; Playbook · ' + esc(P.version || "") + "</p>" +
      '<h1 class="display" style="font-size:clamp(1.8rem,5vw,2.7rem)">스스로 채점하고,<br><em>룰을 고친다</em></h1>' +
      '<p class="lede">브리핑은 매 회차 채점된다. 점수는 자랑이 아니라 다음 회차에서 버릴 패턴과 새로 확인할 1차 데이터를 정하기 위해 존재한다.</p>' +

      '<section class="sec">' + sectionHead("SCORE", "직전 회차 자가평가", S.gradedLabel || "") +
      '<div class="card"><div class="score-hero">' +
      '<div class="ring" style="--pct:' + pct + '"><div class="in"><b>' + total + "</b><span>/ " + (S.max || 100) + " POINTS</span></div></div>" +
      '<div class="crit">' + crit + "</div></div>" +
      (S.verdict ? '<p class="tiny" style="margin:16px 0 0;color:var(--ink-3)">' + rich(S.verdict) + "</p>" : "") +
      "</div></section>" +

      (principles ? '<section class="sec">' + sectionHead("GRADE", "채점 기준", "4 × 25 pts") +
        '<div class="callout quiet">' + blockList({ ordered: true, items: S.principles }) + "</div></section>" : "") +

      '<section class="sec">' + sectionHead("LOG", "평가 로그", "Chronological") + logs + "</section>" +

      '<section class="sec">' + sectionHead("RULES", "현재 룰북 · " + (P.version || ""), "Last updated " + (P.updatedLabel || "")) +
      rules +
      (P.watch ? '<div class="callout" style="margin-top:6px"><span class="ct">현재 추적 변수</span>' +
        blockList({ items: P.watch }) + "</div>" : "") +
      "</section>" +

      (changelog ? '<section class="sec">' + sectionHead("VER", "룰북 변경 이력", "Version log") +
        '<div class="changelog">' + changelog + "</div></section>" : "") +
      "</div>";
  }

  /* ----------------------------------------------------------------- shell */

  var VIEWS = { overview: viewOverview, deepdive: viewDeepDive, frontier: viewFrontier, ledger: viewLedger, system: viewSystem };

  function currentView() {
    var h = (location.hash || "#overview").replace("#", "");
    return VIEWS[h] ? h : "overview";
  }

  function render() {
    state.view = currentView();
    app.innerHTML = VIEWS[state.view]();
    document.querySelectorAll("[data-nav]").forEach(function (a) {
      a.classList.toggle("is-active", a.getAttribute("data-nav") === state.view);
      if (a.getAttribute("data-nav") === state.view) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    document.title = "10X Research Desk — " + ({ overview: "Briefing", deepdive: "Deep-Dive", frontier: "Frontier Lab", ledger: "Idea Ledger", system: "Playbook" })[state.view];
  }

  app.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-act]");
    if (!btn) return;
    var act = btn.getAttribute("data-act");
    var val = btn.getAttribute("data-val");
    if (act === "alloc") { state.alloc = val; render(); }
    if (act === "filter") { state.filter = val; render(); }
    if (act === "memo") { state.memoIdx = parseInt(val, 10) || 0; render(); window.scrollTo({ top: 0, behavior: "smooth" }); }
    if (act === "frontier") { state.frontierIdx = parseInt(val, 10) || 0; render(); window.scrollTo({ top: 0, behavior: "smooth" }); }
  });

  window.addEventListener("hashchange", function () {
    render();
    window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
  });

  function fail(err) {
    app.innerHTML = '<div class="view"><div class="callout warn"><span class="ct">데이터 로드 실패</span>' +
      "data/ 폴더의 JSON을 읽지 못했다. <b>" + esc(err && err.message ? err.message : err) + "</b><br>" +
      "publish.sh로 데이터를 생성·검증한 뒤 다시 배포할 것.</div></div>";
    console.error(err);
  }

  function boot() {
    var bust = "?v=" + Date.now();
    Promise.all(FILES.map(function (f) {
      return fetch("data/" + f + ".json" + bust, { cache: "no-store" }).then(function (r) {
        if (!r.ok) throw new Error(f + ".json → HTTP " + r.status);
        return r.json();
      });
    })).then(function (res) {
      FILES.forEach(function (f, i) { D[f] = res[i]; });
      var head = document.getElementById("head-updated");
      if (head) head.textContent = fmtDate(D.meta.updatedAt);
      var fv = document.getElementById("foot-version");
      if (fv) fv.textContent = "DATA " + (D.meta.dataVersion || "—") + " · " + (D.playbook && D.playbook.version ? D.playbook.version.toUpperCase() : "");
      render();
      window.__deskReady = true;
    }).catch(fail);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
