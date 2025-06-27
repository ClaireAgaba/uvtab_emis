// Dynamically show and populate modules field for Modular marksheet generation

let allModules = [];

async function fetchModulesForOccupation(occupationId) {
    // Fetch modules for the selected occupation (Modular: no level)
    if (!occupationId) return [];
    try {
        const resp = await fetch(`/eims/api/modules/?occupation_id=${occupationId}`);
        if (resp.ok) {
            const data = await resp.json();
            if (data && Array.isArray(data.modules)) {
                return data.modules;
            }
        }
    } catch (err) {}
    return [];
}

async function updateModulesField() {
    const regcat = document.getElementById('reg-category-select').value;
    const occId = document.getElementById('occupation-select').value;
    const modulesWrapper = document.getElementById('modules-field');
    const modulesSelect = document.getElementById('modules-select');
    modulesSelect.innerHTML = '';
    if (regcat === 'modular' && occId) {
        modulesWrapper.classList.remove('hidden');
        modulesSelect.disabled = false;
        modulesSelect.innerHTML = '<option value="" disabled>Select modules...</option>';
        const modules = await fetchModulesForOccupation(occId);
        allModules = modules;
        modules.forEach(mod => {
            const opt = document.createElement('option');
            opt.value = mod.id;
            opt.textContent = `${mod.code} - ${mod.name}`;
            modulesSelect.appendChild(opt);
        });
    } else {
        modulesWrapper.classList.add('hidden');
        modulesSelect.disabled = true;
    }
}

// Attach to occupation/category changes
if (document.getElementById('reg-category-select')) {
    document.getElementById('reg-category-select').addEventListener('change', updateModulesField);
}
if (document.getElementById('occupation-select')) {
    document.getElementById('occupation-select').addEventListener('change', updateModulesField);
}
// No need to listen for level-select changes for Modular

// On modal open, also reset modules field
if (typeof openBtn !== 'undefined') {
    openBtn.addEventListener('click', () => {
        const modulesWrapper = document.getElementById('modules-field');
        const modulesSelect = document.getElementById('modules-select');
        if (modulesWrapper && modulesSelect) {
            modulesWrapper.classList.add('hidden');
            modulesSelect.innerHTML = '';
            modulesSelect.disabled = true;
        }
    });
}
