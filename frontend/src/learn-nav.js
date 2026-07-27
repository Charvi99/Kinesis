// Tiny event-bus so any deep "?" chip can jump to the Learn tab + scroll to an
// anchor, without prop-drilling or a router. App listens for 'kinesis:learn'.
export function openLearn(id = '') {
  window.dispatchEvent(new CustomEvent('kinesis:learn', { detail: id }));
}
