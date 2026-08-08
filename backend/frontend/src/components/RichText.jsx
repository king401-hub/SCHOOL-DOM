/* Renders the HTML that FormattedTextarea stores.

   The editor keeps its content as HTML - <strong>, <em>, <u>, <br> and so on -
   so anywhere that content is dropped into JSX as a plain child, React escapes
   it and the teacher sees the literal tags instead of the formatting. That is
   the Review tab bug. Stripping the tags would fix the symptom by destroying
   the formatting, which is the opposite of what the editor is for, so this
   renders them properly instead.

   Sanitising works by escaping the whole string first and then re-admitting
   only the exact tags on the allowlist. Building up from nothing rather than
   filtering down means no attribute, no URL, and no unclosed-tag trick can
   survive: anything not spelled exactly like an allowed tag stays escaped text.
   That matters because this content is authored by teachers, imported from
   Word and CSV files, and stored server-side - none of which this component
   gets to trust. */

// Inline formatting the editor produces, plus the block tags older imported
// content arrives with. No attributes are permitted on any of them.
const VOID_TAGS = ["br"];
const PAIRED_TAGS = ["strong", "b", "em", "i", "u", "sub", "sup", "p", "ul", "ol", "li", "blockquote"];

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function sanitizeRichText(value) {
  if (value === null || value === undefined) return "";
  let out = escapeHtml(value);

  VOID_TAGS.forEach((tag) => {
    // <br>, <br/> and <br /> all mean the same thing.
    out = out.replace(new RegExp(`&lt;${tag}\\s*/?&gt;`, "gi"), `<${tag}>`);
  });

  PAIRED_TAGS.forEach((tag) => {
    out = out.replace(new RegExp(`&lt;${tag}&gt;`, "gi"), `<${tag}>`);
    out = out.replace(new RegExp(`&lt;/${tag}&gt;`, "gi"), `</${tag}>`);
  });

  return out;
}

/* True when the value has nothing a reader would see - used to decide whether
   to show placeholder text, since "<p></p><br>" looks empty but is not "". */
export function isRichTextEmpty(value) {
  return !String(value || "")
    .replace(/<[^>]*>/g, "")
    .replace(/&nbsp;/gi, " ")
    .trim();
}

export default function RichText({ value, className = "", as: Tag = "div", placeholder = null, ...props }) {
  if (isRichTextEmpty(value)) {
    return placeholder ? <Tag className={`rich-text ${className}`.trim()} {...props}>{placeholder}</Tag> : null;
  }
  return (
    <Tag
      {...props}
      className={`rich-text ${className}`.trim()}
      dangerouslySetInnerHTML={{ __html: sanitizeRichText(value) }}
    />
  );
}
