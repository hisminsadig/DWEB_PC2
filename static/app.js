document.addEventListener("DOMContentLoaded", () => {
  const deleteForms = document.querySelectorAll('form[action*="/gastos/"][action$="/eliminar"]');
  if (!deleteForms.length) return;

  const dialog = document.createElement("dialog");
  dialog.className = "confirm-dialog";
  dialog.setAttribute("aria-labelledby", "confirm-title");
  dialog.innerHTML = `
    <div class="confirm-content">
      <div class="confirm-icon" aria-hidden="true">!</div>
      <div>
        <h2 id="confirm-title">Confirmar eliminación</h2>
        <p>¿Estás seguro de que deseas eliminar este gasto?</p>
      </div>
    </div>
    <div class="confirm-actions">
      <button type="button" class="confirm-cancel">Cancelar</button>
      <button type="button" class="confirm-accept">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>
        Aceptar
      </button>
    </div>`;
  document.body.appendChild(dialog);

  let pendingForm = null;
  document.addEventListener("submit", (event) => {
    const form = event.target.closest('form[action*="/gastos/"][action$="/eliminar"]');
    if (!form) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    pendingForm = form;
    dialog.showModal();
  }, true);

  dialog.querySelector(".confirm-cancel").addEventListener("click", () => {
    pendingForm = null;
    dialog.close();
  });
  dialog.querySelector(".confirm-accept").addEventListener("click", () => {
    if (!pendingForm) return;
    const form = pendingForm;
    pendingForm = null;
    dialog.close();
    form.submit();
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      pendingForm = null;
      dialog.close();
    }
  });
});
