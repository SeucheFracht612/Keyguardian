export function setBusy(form, busy) {
  for (const element of form.elements) {
    element.disabled = busy;
  }
}
