(() => {
    const sidebar = document.querySelector(".app-sidebar");
    const menu = document.querySelector(".mobile-menu");

    if (!sidebar || !menu) {
        return;
    }

    let backdrop = document.querySelector(".sidebar-backdrop");

    if (!backdrop) {
        backdrop = document.createElement("div");
        backdrop.className = "sidebar-backdrop";
        document.body.appendChild(backdrop);
    }

    function closeSidebar() {
        sidebar.classList.remove("open");
        backdrop.classList.remove("show");
        document.body.classList.remove("sidebar-open");
        menu.setAttribute("aria-expanded", "false");
    }

    function openSidebar() {
        sidebar.classList.add("open");
        backdrop.classList.add("show");
        document.body.classList.add("sidebar-open");
        menu.setAttribute("aria-expanded", "true");
    }

    menu.setAttribute("aria-expanded", "false");

    menu.addEventListener("click", () => {
        if (sidebar.classList.contains("open")) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });

    backdrop.addEventListener("click", closeSidebar);

    document.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            closeSidebar();
        }
    });

    sidebar.querySelectorAll("a").forEach(link => {
        link.addEventListener("click", closeSidebar);
    });

    window.addEventListener("resize", () => {
        if (window.innerWidth > 760) {
            closeSidebar();
        }
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

        window.addEventListener("beforeunload", event => {
            if (!changed) {
                return;
            }
            event.preventDefault();
            event.returnValue = "";
        });
    });
})();
