// static/app.js

function showToast(text, variant = "info") {
  const container = document.querySelector(".toast-container");
  if (!container) return;

  const el = document.createElement("div");
  el.className = `toast align-items-center text-bg-${variant}`;
  el.setAttribute("role", "alert");
  el.setAttribute("aria-live", "assertive");
  el.setAttribute("aria-atomic", "true");
  el.dataset.bsDelay = "5000";

  el.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${text}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto"
              data-bs-dismiss="toast" aria-label="Close"></button>
    </div>
  `;

  container.appendChild(el);
  const toast = new bootstrap.Toast(el);
  toast.show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}

document.addEventListener("DOMContentLoaded", () => {
  // Показать серверные flash-тосты
  document.querySelectorAll(".toast").forEach((el) => {
    const t = new bootstrap.Toast(el);
    t.show();
  });

  // Bootstrap validation helper
  document.querySelectorAll(".needs-validation").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    });
  });

  // Каскад поиска: пациент -> visit_datetime
  const cascadePatient = document.getElementById("cascadePatient");
  const cascadeVisit = document.getElementById("cascadeVisit");

  if (cascadePatient && cascadeVisit) {
    cascadePatient.addEventListener("change", async () => {
      cascadeVisit.innerHTML = `<option value="">(загрузка...)</option>`;
      const pid = cascadePatient.value;
      if (!pid) {
        cascadeVisit.innerHTML = `<option value="">(сначала выберите пациента)</option>`;
        return;
      }

      try {
        const res = await fetch(`/api/options/visits-by-patient?patient_id=${encodeURIComponent(pid)}`);
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || "Ошибка");

        if (!data.items.length) {
          cascadeVisit.innerHTML = `<option value="">(нет приёмов)</option>`;
          return;
        }

        cascadeVisit.innerHTML = `<option value="">(любой)</option>`;
        for (const item of data.items) {
          const opt = document.createElement("option");
          // item.value приходит как "YYYY-MM-DD HH:MM:SS"
          // а search ожидает datetime-local? — мы позволяем отправлять как есть
          opt.value = item.value;
          opt.textContent = item.label;
          cascadeVisit.appendChild(opt);
        }
      } catch (err) {
        cascadeVisit.innerHTML = `<option value="">(ошибка загрузки)</option>`;
        showToast(`Ошибка каскада: ${err.message}`, "danger");
      }
    });
  }
});
