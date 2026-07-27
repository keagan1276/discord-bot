	(() => {
const sidebar = document.querySelector(".app-sidebar");
const menu = document.querySelector(".mobile-menu");

let backdrop = document.querySelector(".sidebar-backdrop");

if (!backdrop) {
    backdrop = document.createElement("div");
    backdrop.className = "sidebar-backdrop";
    document.body.appendChild(backdrop);
}

function closeSidebar() {
    sidebar.classList.remove("open");
    backdrop.classList.remove("show");
}

function openSidebar() {
    sidebar.classList.add("open");
    backdrop.classList.add("show");
}

menu?.addEventListener("click", () => {

    if (sidebar.classList.contains("open")) {

        closeSidebar();

    } else {

        openSidebar();

    }

});

backdrop.addEventListener("click", closeSidebar);

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