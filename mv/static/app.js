// List filters and site search. Every page works without this file except filtering and search.
(function () {
  function fold(s) { return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }

  document.querySelectorAll(".filter").forEach(function (box) {
    var items = Array.prototype.slice.call(document.querySelectorAll(box.dataset.target));
    var input = box.querySelector("input");
    var shown = box.querySelector(".shown");
    var on = {};
    function apply() {
      var q = fold(input && input.value.trim()), n = 0;
      items.forEach(function (li) {
        var ok = !q || fold(li.dataset.n || li.textContent).indexOf(q) >= 0;
        Object.keys(on).forEach(function (k) {
          if (on[k].length && on[k].indexOf(li.dataset[k] || "") < 0) ok = false;
        });
        li.classList.toggle("hide", !ok);
        if (ok) n++;
      });
      var active = q || Object.keys(on).some(function (k) { return on[k].length; });
      if (shown) shown.textContent = active ? n + " of " + items.length + " shown" : "";
    }
    box.querySelectorAll("button.chip").forEach(function (b) {
      var k = b.dataset.k, v = b.dataset.v;
      on[k] = on[k] || [];
      b.addEventListener("click", function () {
        var p = b.getAttribute("aria-pressed") === "true";
        b.setAttribute("aria-pressed", p ? "false" : "true");
        on[k] = p ? on[k].filter(function (x) { return x !== v; }) : on[k].concat([v]);
        apply();
      });
    });
    if (input) input.addEventListener("input", apply);
  });

  var res = document.getElementById("results");
  if (!res) return;
  var input = document.getElementById("q");
  var status = document.getElementById("status");
  var data = null;
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function run() {
    var q = fold(input.value.trim());
    try { var u = new URL(location.href); if (q) u.searchParams.set("q", input.value.trim()); else u.searchParams.delete("q"); history.replaceState(null, "", u); } catch (e) {}
    if (!q) { res.innerHTML = ""; status.textContent = ""; return; }
    var words = q.split(/\s+/), out = [];
    for (var i = 0; i < data.length && out.length < 300; i++) {
      var r = data[i], hay = fold(r[3]);
      if (words.every(function (w) { return hay.indexOf(w) >= 0; })) out.push(r);
    }
    status.textContent = out.length + (out.length === 300 ? "+" : "") + " results";
    res.innerHTML = out.map(function (r) {
      return '<li><a href="' + r[1] + '">' + esc(r[2]) + '</a> <span class="tag">' + esc(r[0]) + "</span>" +
        (r[4] ? '<span class="sub">' + esc(r[4]) + "</span>" : "") + "</li>";
    }).join("");
  }
  fetch("search.json").then(function (r) { return r.json(); }).then(function (d) {
    data = d;
    try { var p = new URL(location.href).searchParams.get("q"); if (p) input.value = p; } catch (e) {}
    input.addEventListener("input", run);
    run();
  });
})();
