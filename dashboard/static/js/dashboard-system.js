(() => {
    const sidebarToggle = document.querySelector("[data-sidebar-toggle]");

    if (sidebarToggle) {
        sidebarToggle.addEventListener("click", () => {
            document.body.classList.toggle("sidebar-open");
        });
    }

    document.querySelectorAll("[data-preview-source]").forEach(source => {
        const key = source.dataset.previewSource;
        const target = document.querySelector(`[data-preview-target="${key}"]`);

        if (!target) return;

        function update() {
            target.textContent = source.value || source.placeholder || "Preview";
        }

        update();
        source.addEventListener("input", update);
    });

    document.querySelectorAll("form").forEach(form => {
        let changed = false;

        const saveText = form.querySelector(".save-bar span");

        form.addEventListener("input", () => {
            changed = true;

            if (saveText) {
                saveText.textContent = "You have unsaved changes.";
            }
        });

        form.addEventListener("submit", () => {
            changed = false;
        });

        window.addEventListener("beforeunload", (event) => {
            if (!changed) return;

            event.preventDefault();
            event.returnValue = "";
        });
    });
})();