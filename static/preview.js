const fileInput = document.querySelector("#fileInput");
const preview = document.querySelector("#preview");
const placeholder = document.querySelector("#placeholder");

fileInput.addEventListener("change", () => {
  const selectedFile = fileInput.files?.[0] ?? null;
  if (!selectedFile) {
    preview.style.display = "none";
    placeholder.style.display = "block";
    return;
  }

  preview.src = URL.createObjectURL(selectedFile);
  preview.style.display = "block";
  placeholder.style.display = "none";
});
