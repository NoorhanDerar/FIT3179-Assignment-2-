/*
   Renders every chart so it FILLS its white card.
   each chart is first drawn off-screen at two test sizes. From the
   two results we learn how much of the final size is fixed (titles, legends, axes)
   and how much grows with the plot, then we solve for the plot size that makes the
   finished chart exactly as big as the card. All cards have the same shape, so all
   charts end up the same size. Text stays at its normal size (nothing is stretched). */

// Chart settings shared by every chart.
var embedOptions = {
    renderer: "svg",
    actions: { export: true, source: true, compiled: false, editor: false },
    config: {
        font: "Inter",
        view: { stroke: null },
        padding: { top: 8, right: 12, bottom: 8, left: 8 },
        title: {
            font: "Inter", fontSize: 17, fontWeight: 700, color: "#0F1B2D",
            anchor: "start", frame: "bounds", offset: 14,
            subtitleFont: "Inter", subtitleColor: "#45526A", subtitleFontSize: 13,
            subtitlePadding: 6
        },
        axis: {
            labelFont: "Inter", titleFont: "Inter",
            labelColor: "#45526A", titleColor: "#45526A",
            labelFontSize: 12, titleFontSize: 12, titleFontWeight: 500,
            labelPadding: 6, titlePadding: 12,
            domainColor: "#C5CEDC", tickColor: "#C5CEDC", gridColor: "#E3E8F0"
        },
        // Legends sit on the right of the chart, stacked vertically.
        legend: {
            orient: "right", direction: "vertical",
            labelFont: "Inter", titleFont: "Inter",
            labelColor: "#0F1B2D", titleColor: "#45526A",
            labelFontSize: 12, titleFontSize: 12,
            titleLimit: 220, labelLimit: 200,
            offset: 24, padding: 12,
            titlePadding: 8, labelOffset: 6,
            rowPadding: 8,
            gradientLength: 160, gradientThickness: 10
        },
        header: { labelFont: "Inter", titleFont: "Inter", labelColor: "#0F1B2D", labelPadding: 8, titlePadding: 8 }
    }
};

var charts = [
    ["#restaurant_map", "js/proportional_symbol_restaurant_map.vl.json"],
    ["#map-dorling", "js/dorling_states.json"],
    ["#waffle", "js/waffle_reviews.vl.json"],
    ["#heatmap", "js/heatmap_city_stars.vg.json"],
    ["#dumbbell", "js/dumbell_platform.vg.json"],
    ["#boxplot", "js/boxplot_ratings.vl.json"],
    ["#ridgeline", "js/ridgeline_ratings.vl.json"],
    ["#lolipop_chart", "js/lolipop_chart.json"],
    ["#words", "js/butterfly_words.vl.json"],
    ["#income_map", "js/choropleth_income.vl.json"],
    ["#scatter_income", "js/scatter_income_5star.vg.json"],
    ["#bump_chart", "js/bump_chart.json"]
];


var HOOKS = {
    // The state circles are placed by hand, so they must grow in step with the layout
    // (same factor in both directions, and circle AREA grows with the factor squared).
    "js/dorling_states.json": {
        uniform: true,
        apply: function (spec, fx) {
            spec.layer[0].encoding.size.scale.range = [0, 6527 * fx * fx];
        }
    },
    // The ridgeline humps overlap their neighbours; the overlap must grow with the row height.
    "js/ridgeline_ratings.vl.json": {
        apply: function (spec) {
            spec.encoding.y.scale.range = [spec.height, -spec.height / 2];
        }
    }
};

var views = {};

function clone(o) { return JSON.parse(JSON.stringify(o)); }

// Multiply every numeric width/height in a spec (including inside facets and concats).
function scaleSpec(node, fx, fy) {
    if (Array.isArray(node)) { node.forEach(function (n) { scaleSpec(n, fx, fy); }); return; }
    if (node && typeof node === "object") {
        Object.keys(node).forEach(function (k) {
            var v = node[k];
            if (k === "values") return;
            if (k === "width" && typeof v === "number") node[k] = Math.max(20, Math.round(v * fx));
            else if (k === "height" && typeof v === "number") node[k] = Math.max(20, Math.round(v * fy));
            else scaleSpec(v, fx, fy);
        });
    }
}

// Remove per-chart legend positions so the shared "legends on the right" setting applies everywhere.
function cleanLegends(node) {
    if (Array.isArray(node)) { node.forEach(cleanLegends); return; }
    if (node && typeof node === "object") {
        Object.keys(node).forEach(function (k) {
            if (k === "legend" && node[k] && typeof node[k] === "object") {
                delete node[k].orient;
                delete node[k].direction;
            }
            cleanLegends(node[k]);
        });
    }
}

function wrapText(text, maxChars) {
    var words = String(text).split(/\s+/), lines = [], line = "";
    words.forEach(function (w) {
        if ((line + " " + w).trim().length > maxChars) { lines.push(line); line = w; }
        else { line = (line + " " + w).trim(); }
    });
    if (line) lines.push(line);
    return lines;
}

// Long titles/subtitles would make a chart wider than its card, so wrap them onto several lines.
function wrapTitle(spec, W) {
    var t = spec.title;
    if (!t || typeof t !== "object" || Array.isArray(t)) return;
    if (typeof t.subtitle === "string") {
        var s = wrapText(t.subtitle, Math.floor(W / 7.2));
        if (s.length > 1) t.subtitle = s;
    }
    if (typeof t.text === "string") {
        var x = wrapText(t.text, Math.floor(W / 10));
        if (x.length > 1) t.text = x;
    }
}

function build(base, hook, fx, fy) {
    var s = clone(base);
    scaleSpec(s, fx, fy);
    if (hook && hook.apply) hook.apply(s, fx, fy);
    return s;
}

// Draw off-screen and report the finished size.
async function measure(base, hook, fx, fy) {
    var holder = document.createElement("div");
    holder.style.cssText = "position:absolute;left:-99999px;top:0;visibility:hidden;";
    document.body.appendChild(holder);
    var opts = Object.assign({}, embedOptions, { actions: false });
    var res = await vegaEmbed(holder, build(base, hook, fx, fy), opts);
    var svg = holder.querySelector("svg.marks") || holder.querySelector("svg");
    var out = { w: parseFloat(svg.getAttribute("width")), h: parseFloat(svg.getAttribute("height")) };
    res.finalize();
    document.body.removeChild(holder);
    return out;
}

function clamp(v) { return Math.min(5, Math.max(0.25, v)); }

async function renderChart(sel, url) {
    var box = document.querySelector(sel);
    var cs = getComputedStyle(box);
    var narrow = window.innerWidth <= 700;

    // inner size of the white card
    var W = box.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    var H = box.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
    if (narrow) { W = Math.max(W, 620); H = Math.round(W * 0.8); }   // phones: scroll sideways instead of shrinking text

    var text = await (await fetch(url)).text();
    // use Inter everywhere, and the darker TripAdvisor orange (matches --trip in style.css)
    var base = JSON.parse(text.replace(/DM Sans/g, "Inter").replace(/#D9480F/gi, "#C2410C"));
    cleanLegends(base);
    wrapTitle(base, W);
    var hook = HOOKS[url];

    // two test sizes tell us the fixed part (titles, legends, axes) and the growing part (the plot)
    var m1 = await measure(base, hook, 1, 1);
    var m2 = await measure(base, hook, 1.5, 1.5);
    var kw = 2 * (m2.w - m1.w), bw = m1.w - kw;
    var kh = 2 * (m2.h - m1.h), bh = m1.h - kh;
    var fx = kw > 1 ? clamp((W - bw) / kw) : 1;
    var fy = kh > 1 ? clamp((H - bh) / kh) : 1;
    if (hook && hook.uniform) { fx = fy = Math.min(fx, fy); }

    // refine: correct any leftover error (legends can wrap, text can round)
    for (var i = 0; i < 2; i++) {
        var m = await measure(base, hook, fx, fy);
        var dx = W - m.w, dy = H - m.h;
        if (Math.abs(dx) < 3 && Math.abs(dy) < 3) break;
        if (hook && hook.uniform) {
            var step = Math.min(kw > 1 ? dx / kw : Infinity, kh > 1 ? dy / kh : Infinity);
            if (isFinite(step)) { fx = fy = clamp(fx + step); }
        } else {
            if (kw > 1) fx = clamp(fx + dx / kw);
            if (kh > 1) fy = clamp(fy + dy / kh);
        }
    }

    if (views[sel]) { views[sel].finalize(); }
    var res = await vegaEmbed(sel, build(base, hook, fx, fy), embedOptions);
    views[sel] = res;

    var svg = box.querySelector("svg.marks") || box.querySelector(":scope > svg");
    if (svg) {
        var w = parseFloat(svg.getAttribute("width")), h = parseFloat(svg.getAttribute("height"));
        if (w && h && !svg.getAttribute("viewBox")) svg.setAttribute("viewBox", "0 0 " + w + " " + h);
        svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
        svg.style.display = "block";
    }
}

async function renderAll() {
    for (var i = 0; i < charts.length; i++) {
        var c = charts[i];
        try {
            await renderChart(c[0], c[1]);
        } catch (err) {
            console.error("Chart failed:", c[1], err);
            document.querySelector(c[0]).textContent = "Could not load " + c[1];
        }
    }
}

// Redraw if the window width changes (so the charts keep filling their cards).
var lastWidth = window.innerWidth, resizeTimer;
window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
        if (Math.abs(window.innerWidth - lastWidth) > 8) {
            lastWidth = window.innerWidth;
            renderAll();
        }
    }, 300);
});

// Wait for the Inter font so Vega measures text correctly.
if (document.fonts && document.fonts.load) {
    Promise.all([
        document.fonts.load("400 12px Inter"),
        document.fonts.load("600 12px Inter"),
        document.fonts.load("700 12px Inter")
    ]).then(renderAll, renderAll);
} else {
    renderAll();
}