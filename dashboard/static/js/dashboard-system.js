	(() => {
	   const sidebar = document.querySelector(".app-sidebar");
	const button = document.querySelector("[data-sidebar-toggle]");

	let backdrop = document.querySelector(".sidebar-backdrop");

	if(!backdrop){

		backdrop=document.createElement("div");

		backdrop.className="sidebar-backdrop";

		document.body.appendChild(backdrop);

	}

	button?.addEventListener("click",()=>{

		sidebar.classList.toggle("open");

		backdrop.classList.toggle("show");

	});

	backdrop.addEventListener("click",()=>{

		sidebar.classList.remove("open");

		backdrop.classList.remove("show");

	});
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