(() => {
    const FIELD_TYPES = {
        channel: "channels",
        channel_id: "channels",
        ticket_channel: "channels",
        log_channel: "channels",
        menu_channel_id: "channels",
        staff_role_id: "roles",
        role_id: "roles",
        category_id: "categories"
    };

    const forms = [...document.querySelectorAll("form")];
    if (!forms.length) return;

    const fields = [...document.querySelectorAll("input[name], select[name]")]
        .filter(element => FIELD_TYPES[element.name]);

    if (!fields.length) return;

    const style = document.createElement("style");
    style.textContent = `
        .discord-selector-panel {
            background: rgba(20, 0, 0, 0.92);
            border: 2px solid #ff3300;
            border-radius: 20px;
            padding: 22px;
            max-width: 800px;
            margin-bottom: 25px;
            box-shadow: 0 0 25px red;
        }
        .discord-selector-panel h3 { color: #ffd700; margin-top: 0; }
        .discord-selector-panel p { color: #ffcccc; }
        .discord-select {
            width: 90%;
            padding: 12px;
            margin: 10px 0 18px;
            background: #220000;
            border: 2px solid #ff3300;
            border-radius: 10px;
            color: #ffd700;
            font-size: 16px;
        }
        .discord-select:focus {
            outline: none;
            border-color: orange;
            box-shadow: 0 0 15px orange;
        }
        .discord-selector-status { color: #ffcccc; font-size: 14px; }
    `;
    document.head.appendChild(style);

    const firstForm = forms[0];
    const panel = document.createElement("div");
    panel.className = "discord-selector-panel";
    panel.innerHTML = `
        <h3>🌍 Discord Server</h3>
        <p>Select the server whose channels, roles and categories you want to use.</p>
        <select id="global-guild-select" class="discord-select">
            <option value="">Loading servers...</option>
        </select>
        <div id="discord-selector-status" class="discord-selector-status"></div>
    `;
    firstForm.prepend(panel);

    const guildSelect = panel.querySelector("#global-guild-select");
    const status = panel.querySelector("#discord-selector-status");
    const originalValues = new Map(fields.map(field => [field.name, field.value || ""]));
    const upgraded = [];

    function labelFor(element) {
        const direct = element.previousElementSibling;
        if (direct && direct.tagName === "LABEL") return direct.textContent.trim();
        return element.name.replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
    }

    function upgradeField(field) {
        if (field.tagName === "SELECT" && field.dataset.discordUpgraded) return field;

        const select = document.createElement("select");
        select.name = field.name;
        select.className = `${field.className || ""} discord-select`.trim();
        select.dataset.discordUpgraded = "true";
        select.dataset.sourceType = FIELD_TYPES[field.name];
        select.dataset.originalValue = field.value || "";
        select.innerHTML = `<option value="">Choose ${labelFor(field)}</option>`;

        field.replaceWith(select);
        upgraded.push(select);
        return select;
    }

    fields.forEach(upgradeField);

    function optionText(item, type) {
        if (type === "channels") return `#${item.name}`;
        if (type === "roles") return `@${item.name}`;
        return item.name;
    }

    function populateSelect(select, items) {
        const type = select.dataset.sourceType;
        const previous = select.dataset.originalValue || select.value;
        const firstText = type === "channels" ? "Choose a channel" :
            type === "roles" ? "Choose a role" : "Choose a category";

        select.innerHTML = `<option value="">${firstText}</option>`;

        items.forEach(item => {
            if (type === "channels" && item.type && !["text", "news", "forum"].includes(item.type)) {
                return;
            }
            const option = document.createElement("option");
            option.value = item.id;
            option.textContent = optionText(item, type);
            if (String(item.id) === String(previous)) option.selected = true;
            select.appendChild(option);
        });
    }

    async function loadGuildData(guildId) {
        status.textContent = "Loading Discord channels, roles and categories...";
        try {
            const response = await fetch(`/api/guild/${guildId}/all`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();

            upgraded.forEach(select => {
                populateSelect(select, data[select.dataset.sourceType] || []);
            });
            status.textContent = "✅ Discord data loaded.";
        } catch (error) {
            status.textContent = `❌ Could not load Discord data: ${error.message}`;
        }
    }

    async function loadGuilds() {
        try {
            const response = await fetch("/api/guilds");
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const guilds = await response.json();

            guildSelect.innerHTML = '<option value="">Choose a server</option>';
            guilds.forEach(guild => {
                const option = document.createElement("option");
                option.value = guild.id;
                option.textContent = guild.name;
                guildSelect.appendChild(option);
            });

            if (guilds.length === 1) {
                guildSelect.value = guilds[0].id;
                await loadGuildData(guilds[0].id);
            } else if (!guilds.length) {
                status.textContent = "No Discord servers were returned by the bot API.";
            }
        } catch (error) {
            guildSelect.innerHTML = '<option value="">Bot API unavailable</option>';
            status.textContent = `❌ Could not reach the bot API: ${error.message}`;
        }
    }

    guildSelect.addEventListener("change", () => {
        if (guildSelect.value) loadGuildData(guildSelect.value);
    });

    loadGuilds();
})();
