(() => {
  "use strict";

  const allowedTypes = new Set(["image/png", "image/jpeg", "image/webp"]);
  const maxUploadMb = Number(document.body.dataset.maxUploadMb || 5);
  const maxUploadBytes = maxUploadMb * 1024 * 1024;

  const form = document.querySelector("#generation-form");
  const nameInput = document.querySelector("#product-name");
  const descriptionInput = document.querySelector("#description");
  const imageInput = document.querySelector("#product-image");
  const uploadZone = document.querySelector("#upload-zone");
  const preview = document.querySelector("#image-preview");
  const previewImage = document.querySelector("#preview-image");
  const previewName = document.querySelector("#preview-name");
  const removeImage = document.querySelector("#remove-image");
  const submitButton = document.querySelector("#generate-button");
  const notice = document.querySelector("#form-notice");
  const jobsList = document.querySelector("#jobs-list");
  const jobsLoading = document.querySelector("#jobs-loading");
  const jobsEmpty = document.querySelector("#jobs-empty");
  const jobsError = document.querySelector("#jobs-error");
  const modal = document.querySelector("#result-modal");
  const modalTitle = document.querySelector("#modal-title");
  const modalImage = document.querySelector("#modal-image");
  const modalOpenFull = document.querySelector("#modal-open-full");
  let previewUrl = null;
  let isSubmitting = false;

  const errors = {
    product_name: document.querySelector("#product-name-error"),
    description: document.querySelector("#description-error"),
    product_image: document.querySelector("#product-image-error"),
  };

  function setError(field, message = "") {
    errors[field].textContent = message;
    const input = field === "product_name"
      ? nameInput
      : field === "description" ? descriptionInput : uploadZone;
    input.classList.toggle("invalid", Boolean(message));
  }

  function validateImage(file) {
    if (!file) return "Choose a product image.";
    if (!allowedTypes.has(file.type)) return "Use a PNG, JPEG or WebP image.";
    if (file.size > maxUploadBytes) return `Image must be ${maxUploadMb} MB or smaller.`;
    return "";
  }

  function validateForm() {
    const nameError = nameInput.value.trim() ? "" : "Enter a product name.";
    const descriptionError = descriptionInput.value.trim() ? "" : "Enter a short description.";
    const imageError = validateImage(imageInput.files[0]);
    setError("product_name", nameError);
    setError("description", descriptionError);
    setError("product_image", imageError);
    return !(nameError || descriptionError || imageError);
  }

  function clearPreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    imageInput.value = "";
    previewImage.removeAttribute("src");
    preview.hidden = true;
    uploadZone.hidden = false;
    setError("product_image");
  }

  imageInput.addEventListener("change", () => {
    const file = imageInput.files[0];
    const error = validateImage(file);
    setError("product_image", error);
    if (error) {
      clearPreview();
      setError("product_image", error);
      return;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);
    previewImage.src = previewUrl;
    previewName.textContent = file.name;
    preview.hidden = false;
    uploadZone.hidden = true;
  });

  removeImage.addEventListener("click", clearPreview);
  nameInput.addEventListener("input", () => setError("product_name"));
  descriptionInput.addEventListener("input", () => setError("description"));

  function setSubmitting(active) {
    isSubmitting = active;
    submitButton.disabled = active;
    submitButton.classList.toggle("loading", active);
    submitButton.querySelector(".button-label").textContent =
      active ? "Submitting…" : "Generate preview";
  }

  function showNotice(message, type) {
    notice.textContent = message;
    notice.className = `notice ${type}`;
    notice.hidden = false;
  }

  async function apiError(response) {
    try {
      const body = await response.json();
      if (Array.isArray(body.detail)) {
        return body.detail.map((item) => item.msg).join(" ");
      }
      return body.detail || "The request could not be completed.";
    } catch {
      return "The service returned an unexpected response. Please try again.";
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (isSubmitting || !validateForm()) return;

    setSubmitting(true);
    notice.hidden = true;
    try {
      const response = await fetch("/generate", {
        method: "POST",
        body: new FormData(form),
      });
      if (!response.ok) throw new Error(await apiError(response));
      const job = await response.json();
      form.reset();
      clearPreview();
      showNotice(`Job queued successfully · ${job.id.slice(0, 8)}`, "success");
      await loadJobs();
    } catch (error) {
      showNotice(error.message || "Unable to submit the job. Please try again.", "error");
    } finally {
      setSubmitting(false);
    }
  });

  function escapeHtml(value) {
    const element = document.createElement("div");
    element.textContent = value ?? "";
    return element.innerHTML;
  }

  function formatDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Unknown time";
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  }

  function shortDescription(value) {
    if (value.length <= 150) return value;
    return `${value.slice(0, 147)}…`;
  }

  function jobCard(job) {
    const completed = job.status === "completed" && job.result_url;
    const prompt = job.generated_prompt
      ? `<details class="prompt"><summary>Generated prompt</summary><p>${escapeHtml(job.generated_prompt)}</p></details>`
      : "";
    const error = job.status === "failed"
      ? `<div class="job-error"><strong>Generation failed</strong><p>${escapeHtml(job.error_message || "An unexpected error occurred.")}</p></div>`
      : "";
    const result = completed
      ? `<div class="job-result">
          <img src="${escapeHtml(job.result_url)}" alt="Generated preview for ${escapeHtml(job.product_name)}" loading="lazy">
          <div class="result-actions">
            <button class="secondary-button view-result" type="button"
                    data-url="${escapeHtml(job.result_url)}"
                    data-name="${escapeHtml(job.product_name)}">View result</button>
            <div class="result-links">
              <a class="text-link" href="${escapeHtml(job.result_url)}" target="_blank" rel="noopener">Open full image ↗</a>
              <button class="delete-button" type="button"
                      data-job-id="${escapeHtml(job.id)}"
                      data-name="${escapeHtml(job.product_name)}">Delete</button>
            </div>
          </div>
        </div>`
      : "";

    return `<article class="job-card">
      <div class="job-card-header">
        <div>
          <h3>${escapeHtml(job.product_name)}</h3>
          <p class="created-time">${formatDate(job.created_at)}</p>
        </div>
        <span class="status-badge status-${escapeHtml(job.status)}">
          <span aria-hidden="true"></span>${escapeHtml(job.status)}
        </span>
      </div>
      <p class="job-description">${escapeHtml(shortDescription(job.description))}</p>
      ${prompt}${error}${result}
    </article>`;
  }

  async function loadJobs() {
    try {
      const response = await fetch("/jobs", { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(await apiError(response));
      const jobs = await response.json();
      jobsList.innerHTML = jobs.map(jobCard).join("");
      jobsLoading.hidden = true;
      jobsEmpty.hidden = jobs.length !== 0;
      jobsError.hidden = true;
    } catch (error) {
      jobsLoading.hidden = true;
      jobsError.textContent = error.message || "Could not load recent jobs.";
      jobsError.hidden = false;
    }
  }

  jobsList.addEventListener("click", (event) => {
    const deleteButton = event.target.closest(".delete-button");
    if (deleteButton) {
      deleteJob(deleteButton);
      return;
    }
    const button = event.target.closest(".view-result");
    if (!button) return;
    modalTitle.textContent = button.dataset.name;
    modalImage.src = button.dataset.url;
    modalImage.alt = `Generated preview for ${button.dataset.name}`;
    modalOpenFull.href = button.dataset.url;
    modal.showModal();
  });

  async function deleteJob(button) {
    const confirmed = window.confirm(
      `Delete the completed job for "${button.dataset.name}"? This cannot be undone.`
    );
    if (!confirmed) return;

    button.disabled = true;
    button.textContent = "Deleting…";
    try {
      const response = await fetch(`/jobs/${encodeURIComponent(button.dataset.jobId)}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error(await apiError(response));
      await loadJobs();
    } catch (error) {
      jobsError.textContent = error.message || "Could not delete the completed job.";
      jobsError.hidden = false;
      button.disabled = false;
      button.textContent = "Delete";
    }
  }

  document.querySelector("#close-modal").addEventListener("click", () => modal.close());
  modal.addEventListener("click", (event) => {
    if (event.target === modal) modal.close();
  });

  loadJobs();
  window.setInterval(loadJobs, 3000);
})();
