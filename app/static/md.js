/* Mini renderizador de Markdown — o suficiente para as explicações do LLM:
 * cabeçalhos, negrito/itálico, `código`, blocos ```, listas, tabelas.
 * Sem dependências. Escapa HTML antes de qualquer coisa (XSS).
 *
 * window.renderMarkdown(text) -> string HTML
 */
(function () {
  "use strict";

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function inline(s) {
    // já vem escapado; aplica ênfases e código inline
    return s
      .replace(/`([^`]+)`/g, function (_, c) { return "<code>" + c + "</code>"; })
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>")
      .replace(/~~([^~]+)~~/g, "<del>$1</del>");
  }

  function tableRow(line) {
    return line
      .replace(/^\||\|$/g, "")
      .split("|")
      .map(function (c) { return c.trim(); });
  }

  window.renderMarkdown = function (src) {
    if (!src) return "";
    var lines = esc(src).replace(/\r\n?/g, "\n").split("\n");
    var out = [];
    var i = 0;

    while (i < lines.length) {
      var line = lines[i];

      // bloco de código ```
      if (/^```/.test(line)) {
        var buf = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
        i++; // fecha ```
        out.push("<pre><code>" + buf.join("\n") + "</code></pre>");
        continue;
      }

      // tabela:  | a | b |   seguida de  | --- | --- |
      if (/^\|.*\|/.test(line) && i + 1 < lines.length && /^\|[\s:|-]+\|/.test(lines[i + 1])) {
        var head = tableRow(line);
        i += 2; // salta cabeçalho + separador
        var rows = [];
        while (i < lines.length && /^\|.*\|/.test(lines[i])) {
          rows.push(tableRow(lines[i]));
          i++;
        }
        var t = '<div class="md-table-wrap"><table><thead><tr>';
        head.forEach(function (h) { t += "<th>" + inline(h) + "</th>"; });
        t += "</tr></thead><tbody>";
        rows.forEach(function (r) {
          t += "<tr>";
          r.forEach(function (c) { t += "<td>" + inline(c) + "</td>"; });
          t += "</tr>";
        });
        t += "</tbody></table></div>";
        out.push(t);
        continue;
      }

      // cabeçalho
      var h = line.match(/^(#{1,4})\s+(.*)$/);
      if (h) {
        var lvl = Math.min(h[1].length + 2, 6); // # -> h3
        out.push("<h" + lvl + ">" + inline(h[2]) + "</h" + lvl + ">");
        i++;
        continue;
      }

      // lista (- ou * ou 1.)
      if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
        var ordered = /^\s*\d+\.\s+/.test(line);
        var items = [];
        while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
          items.push(lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ""));
          i++;
        }
        var tag = ordered ? "ol" : "ul";
        out.push(
          "<" + tag + ">" +
          items.map(function (it) { return "<li>" + inline(it) + "</li>"; }).join("") +
          "</" + tag + ">"
        );
        continue;
      }

      // linha em branco
      if (/^\s*$/.test(line)) { i++; continue; }

      // parágrafo (junta linhas seguidas)
      var para = [line];
      i++;
      while (
        i < lines.length &&
        !/^\s*$/.test(lines[i]) &&
        !/^```/.test(lines[i]) &&
        !/^(#{1,4})\s/.test(lines[i]) &&
        !/^\s*([-*]|\d+\.)\s+/.test(lines[i]) &&
        !/^\|.*\|/.test(lines[i])
      ) {
        para.push(lines[i]);
        i++;
      }
      out.push("<p>" + inline(para.join(" ")) + "</p>");
    }

    return out.join("\n");
  };
})();
