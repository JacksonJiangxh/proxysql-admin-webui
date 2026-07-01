/**
 * HTML sanitization utility using DOMPurify.
 *
 * Use this for any user-provided content that might be rendered as HTML
 * (e.g., dangerouslySetInnerHTML, rich text from users).
 *
 * By default React's JSX auto-escapes text, but this provides defense-in-depth
 * for scenarios where raw HTML must be rendered.
 */

import DOMPurify from 'dompurify'

/**
 * Sanitize an HTML string, removing potentially dangerous elements/attributes.
 *
 * @param html - Raw HTML string from user input or external source
 * @returns Sanitized HTML string safe for rendering via dangerouslySetInnerHTML
 *
 * @example
 * const safeHtml = sanitizeHtml(userProvidedHtml)
 * return <div dangerouslySetInnerHTML={{ __html: safeHtml }} />
 */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html)
}

/**
 * Sanitize a plain text string for use in text-only contexts.
 * Strips all HTML tags, leaving only the text content.
 *
 * @param text - Raw text string that may contain HTML
 * @returns Plain text with all HTML removed
 *
 * @example
 * const cleanText = sanitizeText('<script>alert("xss")</script>Hello')
 * // Returns: "alert("xss")Hello"
 */
export function sanitizeText(text: string): string {
  return DOMPurify.sanitize(text, { ALLOWED_TAGS: [] })
}

export { DOMPurify }
export default sanitizeHtml
