import { useEffect, useRef, type RefObject } from 'react'

/** Contain keyboard focus only while a modal is visible; restore its trigger on close. */
export function useDialogFocus(
  ref: RefObject<HTMLElement | null>,
  active: boolean,
  onClose: () => void,
) {
  const close = useRef(onClose)
  useEffect(() => {
    close.current = onClose
  }, [onClose])
  useEffect(() => {
    const node = ref.current
    if (!active || !node) return
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusables = () =>
      [
        ...node.querySelectorAll<HTMLElement>(
          'button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex="0"]',
        ),
      ].filter((item) => item.getClientRects().length > 0)
    ;(focusables()[0] ?? node).focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        close.current()
        return
      }
      if (event.key !== 'Tab') return
      const items = focusables()
      const first = items[0]
      const last = items.at(-1)
      if (!first) {
        event.preventDefault()
        node.focus()
        return
      }
      if (
        event.shiftKey &&
        (document.activeElement === first || !node.contains(document.activeElement))
      ) {
        event.preventDefault()
        last?.focus()
      } else if (
        !event.shiftKey &&
        (document.activeElement === last || !node.contains(document.activeElement))
      ) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', keydown)
    return () => {
      document.removeEventListener('keydown', keydown)
      document.body.style.overflow = overflow
      if (previous?.isConnected) previous.focus()
    }
  }, [active, ref])
}
