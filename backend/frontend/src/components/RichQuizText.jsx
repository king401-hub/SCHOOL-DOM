import React from "react";

const TOKEN_RE = /(<\/?(?:u|sub|sup|br)\s*\/?>)/gi;

const MATH_REPLACEMENTS = [
  [/\\cup\b/g, "\u222a"],
  [/\\cap\b/g, "\u2229"],
  [/\\emptyset\b/g, "\u2205"],
  [/\\times\b/g, "\u00d7"],
  [/\\div\b/g, "\u00f7"],
  [/\\cdot\b/g, "\u00b7"],
  [/\\pm\b/g, "\u00b1"],
  [/\\approx\b/g, "\u2248"],
  [/\\propto\b/g, "\u221d"],
  [/\\rightarrow\b/g, "\u2192"],
  [/\\to\b/g, "\u2192"],
  [/\\leq\b/g, "\u2264"],
  [/\\geq\b/g, "\u2265"],
  [/\\neq\b/g, "\u2260"],
  [/\\infty\b/g, "\u221e"],
  [/\\in\b/g, "\u2208"],
  [/\\notin\b/g, "\u2209"],
  [/\\subseteq\b/g, "\u2286"],
  [/\\subset\b/g, "\u2282"],
  [/\\supseteq\b/g, "\u2287"],
  [/\\supset\b/g, "\u2283"],
  [/\\degree\b/g, "\u00b0"],
  [/\\circ\b/g, "\u00b0"],
  [/\\Omega\b/g, "\u03a9"],
  [/\\omega\b/g, "\u03c9"],
  [/\\mu\b/g, "\u03bc"],
  [/\\alpha\b/g, "\u03b1"],
  [/\\beta\b/g, "\u03b2"],
  [/\\gamma\b/g, "\u03b3"],
  [/\\delta\b/g, "\u03b4"],
  [/\\Delta\b/g, "\u0394"],
  [/\\theta\b/g, "\u03b8"],
  [/\\lambda\b/g, "\u03bb"],
  [/\\rho\b/g, "\u03c1"],
  [/\\pi\b/g, "\u03c0"],
  [/\\sigma\b/g, "\u03c3"],
  [/\\qquad\b/g, " "],
  [/\\quad\b/g, " "],
  [/\\%/g, "%"],
  [/\\,/g, " "],
  [/\\;/g, " "],
  [/\\:/g, " "],
];

function normalizeMathText(input) {
  const rawText = String(input || "")
    .replace(/\${2}([^$]+)\${2}/g, "$1")
    .replace(/\$([^$\n]+)\$/g, "$1")
    .replace(/\\\((.*?)\\\)/g, "$1")
    .replace(/\\\[(.*?)\\\]/g, "$1")
    .replace(/\\left\b/g, "")
    .replace(/\\right\b/g, "")
    .replace(/\\(?:dfrac|tfrac|frac)\{([^{}]+)\}\{([^{}]+)\}/g, "$1/$2")
    .replace(/\\sqrt\{([^{}]+)\}/g, "\u221a$1")
    .replace(/\\(?:text|mathrm|mathbf|textbf|operatorname|ce)\{([^{}]+)\}/g, "$1")
    .replace(/\\\{/g, "{")
    .replace(/\\\}/g, "}")
    .replace(/#(?=\d)/g, "\u20a6")
    .replace(/\\\s+/g, " ");

  const text = MATH_REPLACEMENTS.reduce(
    (text, [pattern, replacement]) => text.replace(pattern, replacement),
    rawText
  );

  return text
    .replace(/\^\{([^{}]+)\}/g, "<sup>$1</sup>")
    .replace(/_\{([^{}]+)\}/g, "<sub>$1</sub>")
    .replace(/\^([+-]?\d+(?:\.\d+)?)/g, "<sup>$1</sup>")
    .replace(/_([A-Za-z0-9]+)/g, "<sub>$1</sub>")
    .replace(/\b([A-Za-z]+)\/?s(-?\d+)\b/g, "$1s<sup>$2</sup>")
    .replace(/\b((?:c|d)?m)3\b/gi, "$1<sup>3</sup>")
    .replace(/\b(mol|dm|cm|mm)3\b/gi, "$1<sup>3</sup>")
    .replace(/\)(\d+)/g, ")<sub>$1</sub>")
    .replace(/([A-Z][a-z]?)(\d+)/g, "$1<sub>$2</sub>")
    .replace(/\\([A-Za-z]+)/g, "$1")
    .replace(/\\([#$%&_^{}])/g, "$1")
    .replace(/[{}]/g, "")
    .replace(/[ \t]{2,}/g, " ");
}

function renderTokens(tokens, startIndex = 0, closingTag = "") {
  const nodes = [];
  let index = startIndex;

  while (index < tokens.length) {
    const token = tokens[index];
    const tag = token.match(/^<\/?([a-z]+)\s*\/?>$/i)?.[1]?.toLowerCase();
    const isClosing = /^<\//.test(token);

    if (tag && isClosing) {
      return tag === closingTag ? { nodes, index: index + 1 } : { nodes, index: index + 1 };
    }

    if (tag === "br") {
      nodes.push(<br key={nodes.length} />);
      index += 1;
      continue;
    }

    if (tag && ["u", "sub", "sup"].includes(tag)) {
      const rendered = renderTokens(tokens, index + 1, tag);
      const TagName = tag;
      nodes.push(<TagName key={nodes.length}>{rendered.nodes}</TagName>);
      index = rendered.index;
      continue;
    }

    nodes.push(token);
    index += 1;
  }

  return { nodes, index };
}

export default function RichQuizText({ text }) {
  const normalized = normalizeMathText(text);
  const tokens = normalized.split(TOKEN_RE).filter((part) => part !== "");
  return <>{renderTokens(tokens).nodes}</>;
}
