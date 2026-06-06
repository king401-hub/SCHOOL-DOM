import React from "react";

const TOKEN_RE = /(<\/?(?:u|sub|sup|br)\s*\/?>)/gi;

const MATH_REPLACEMENTS = [
  [/\\cup\b/g, " union "],
  [/\\cap\b/g, " intersection "],
  [/\\emptyset\b/g, "empty set"],
  [/\\times\b/g, " x "],
  [/\\div\b/g, " / "],
  [/\\cdot\b/g, " . "],
  [/\\pm\b/g, "+/-"],
  [/\\approx\b/g, "~"],
  [/\\propto\b/g, "proportional to"],
  [/\\rightarrow\b/g, " -> "],
  [/\\to\b/g, " -> "],
  [/\\leq\b/g, "<="],
  [/\\geq\b/g, ">="],
  [/\\neq\b/g, "!="],
  [/\\infty\b/g, "infinity"],
  [/\\in\b/g, " in "],
  [/\\notin\b/g, " not in "],
  [/\\subseteq\b/g, " subset of or equal to "],
  [/\\subset\b/g, " subset of "],
  [/\\supseteq\b/g, " superset of or equal to "],
  [/\\supset\b/g, " superset of "],
  [/\\degree\b/g, " degrees"],
  [/\\circ\b/g, " degrees"],
  [/\\Omega\b/g, "Ohm"],
  [/\\omega\b/g, "omega"],
  [/\\mu\b/g, "micro"],
  [/\\alpha\b/g, "alpha"],
  [/\\beta\b/g, "beta"],
  [/\\gamma\b/g, "gamma"],
  [/\\delta\b/g, "delta"],
  [/\\Delta\b/g, "Delta"],
  [/\\theta\b/g, "theta"],
  [/\\lambda\b/g, "lambda"],
  [/\\rho\b/g, "rho"],
  [/\\pi\b/g, "pi"],
  [/\\sigma\b/g, "sigma"],
  [/\\qquad\b/g, " "],
  [/\\quad\b/g, " "],
  [/\\%/g, "%"],
  [/\\,/g, " "],
  [/\\;/g, " "],
  [/\\:/g, " "],
];

function normalizeMathText(input) {
  const rawText = String(input || "")
    .replace(/â€¢/g, "-")
    .replace(/â€“|â€”/g, "-")
    .replace(/â€˜|â€™/g, "'")
    .replace(/â€œ|â€�/g, '"')
    .replace(/â€¦/g, "...")
    .replace(/Â°/g, " degrees")
    .replace(/Â±/g, "+/-")
    .replace(/Ã—/g, " x ")
    .replace(/Ã·/g, " / ")
    .replace(/[×]/g, " x ")
    .replace(/[÷]/g, " / ")
    .replace(/[≤]/g, "<=")
    .replace(/[≥]/g, ">=")
    .replace(/[≠]/g, "!=")
    .replace(/[≈]/g, "~")
    .replace(/[→]/g, " -> ")
    .replace(/[√]/g, "sqrt")
    .replace(/[°]/g, " degrees")
    .replace(/[₦]/g, "N")
    .replace(/\${2}([^$]+)\${2}/g, "$1")
    .replace(/\$([^$\n]+)\$/g, "$1")
    .replace(/\\\((.*?)\\\)/g, "$1")
    .replace(/\\\[(.*?)\\\]/g, "$1")
    .replace(/\\left\b/g, "")
    .replace(/\\right\b/g, "")
    .replace(/\\(?:dfrac|tfrac|frac)\{([^{}]+)\}\{([^{}]+)\}/g, "($1)/($2)")
    .replace(/\\sqrt\{([^{}]+)\}/g, "sqrt($1)")
    .replace(/\\(?:text|mathrm|mathbf|textbf|operatorname|ce)\{([^{}]+)\}/g, "$1")
    .replace(/\\\{/g, "{")
    .replace(/\\\}/g, "}")
    .replace(/#(?=\d)/g, "N")
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
