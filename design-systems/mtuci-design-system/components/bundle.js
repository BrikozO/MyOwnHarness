/* @ds-bundle: {"format":4,"namespace":"MtuciSlides","components":[]} */
/* Презентации МТУСИ — помощники для слайдов. Компоненты — CSS-классы mt-* в bundle.css;
   здесь только подсветка Python для .mt-code (классы k s c f t p). Без React и сети. */
(function () {
  var KW = ["def", "return", "if", "elif", "else", "for", "while", "in", "is", "not", "and", "or",
    "lambda", "None", "True", "False", "import", "from", "as", "class", "try", "except", "finally",
    "with", "yield", "global", "nonlocal", "pass", "break", "continue", "raise", "assert", "del", "error"];
  var TYPES = ["str", "int", "float", "bool", "list", "dict", "set", "tuple", "bytes", "object", "Callable"];
  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function span(cls, s) { return '<span class="' + cls + '">' + esc(s) + "</span>"; }
  var RE = /(#[^\n]*)|("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')|(^\s*(?:&gt;&gt;&gt;|>>>|\$)(?= ))|([A-Za-z_][A-Za-z0-9_]*)(\s*\()?|([\s\S])/gm;
  function highlightPython(code) {
    var out = "", m, prevDef = false;
    RE.lastIndex = 0;
    while ((m = RE.exec(code)) !== null) {
      if (m[1]) { out += span("c", m[1]); }
      else if (m[2]) { out += span("s", m[2]); }
      else if (m[3]) { out += span("p", m[3]); }
      else if (m[4]) {
        var w = m[4], call = m[5] || "";
        if (KW.indexOf(w) >= 0) { out += span("k", w); prevDef = (w === "def"); out += esc(call); continue; }
        if (TYPES.indexOf(w) >= 0) { out += span("t", w) + esc(call); }
        else if (prevDef) { out += span("f", w) + esc(call); }
        else { out += esc(w) + esc(call); }
        prevDef = false;
      } else { out += esc(m[6]); if (!/\s/.test(m[6])) prevDef = false; }
    }
    return out;
  }
  /* Подсветить все <pre class="mt-code" data-lang="python"> на странице. */
  function highlightAll(root) {
    var nodes = (root || document).querySelectorAll('pre.mt-code[data-lang="python"]');
    for (var i = 0; i < nodes.length; i++) nodes[i].innerHTML = highlightPython(nodes[i].textContent);
    return nodes.length;
  }
  window.MtuciSlides = { highlightPython: highlightPython, highlightAll: highlightAll };
})();
