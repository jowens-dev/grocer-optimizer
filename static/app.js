// AisleOne Client-Side Application state
let state = {
    shoppingList: [],
    recipes: [],
    recipeDraftIngredients: [],
    selectedRecipe: null,
    tier: 'free',
    shopperPersona: 'single_store_sam',
    clubMemberships: [],
    zipCode: '90210'
};

// Initialize app & auth checks
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    
    // Register Service Worker for PWA mobile installation
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/service-worker.js')
            .then(reg => console.log('[PWA] Service Worker registered successfully:', reg.scope))
            .catch(err => console.error('[PWA] Service Worker registration failed:', err));
    }
});

// Authentication System
async function checkAuth() {
    const token = localStorage.getItem('aisleone_token');
    const authOverlay = document.getElementById('auth-overlay');

    if (!token) {
        authOverlay.classList.remove('hidden');
        return;
    }

    try {
        const response = await fetch('/users/me', {
            headers: { 'Authorization': 'Bearer ' + token }
        });

        if (!response.ok) {
            throw new Error('Session expired');
        }

        const user = await response.json();
        authOverlay.classList.add('hidden');
        
        // Update user status box
        document.getElementById('display-username').innerText = user.username;
        updateUserTierBadge(user.tier);
        
        // Set local state
        state.tier = user.tier;
        state.clubMemberships = user.club_memberships || [];
        state.zipCode = user.zip_code || '90210';
        
        // Initialize inputs based on user settings
        initDashboardSettings();
        
        // Load initial recipes
        loadRecipes();
    } catch (err) {
        console.warn(err);
        localStorage.removeItem('aisleone_token');
        authOverlay.classList.remove('hidden');
    }
}

function updateUserTierBadge(tier) {
    const badge = document.getElementById('display-tier');
    badge.innerText = tier === 'premium' ? 'Premium' : 'Free';
    badge.className = `user-tier badge ${tier === 'premium' ? 'badge-premium' : 'badge-free'}`;
}

function initDashboardSettings() {
    // Set Tier radios
    if (state.tier === 'premium') {
        document.getElementById('tier-premium').checked = true;
    } else {
        document.getElementById('tier-free').checked = true;
    }

    // Set Clubs
    document.getElementById('club-costco').checked = state.clubMemberships.includes('Costco');
    document.getElementById('club-sams').checked = state.clubMemberships.includes('Sams Club');
    document.getElementById('club-bjs').checked = state.clubMemberships.includes("BJ's");

    // Set Zip Code
    document.getElementById('display-zip').value = state.zipCode;

    // Apply visibility/locks based on tier
    applyTierRestrictions();
}

async function registerUser() {
    const uInput = document.getElementById('auth-username');
    const pInput = document.getElementById('auth-password');
    const username = uInput.value.trim();
    const password = pInput.value.trim();

    if (!username || !password) {
        alert('Please fill in both username and password.');
        return;
    }

    try {
        const response = await fetch('/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Registration failed');
        }

        alert('Account created! Logging you in...');
        loginUser();
    } catch (err) {
        alert(err.message);
    }
}

async function loginUser() {
    const uInput = document.getElementById('auth-username');
    const pInput = document.getElementById('auth-password');
    const username = uInput.value.trim();
    const password = pInput.value.trim();

    if (!username || !password) {
        alert('Please fill in both username and password.');
        return;
    }

    try {
        const response = await fetch('/auth/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        if (!response.ok) {
            throw new Error('Invalid username or password');
        }

        const data = await response.json();
        localStorage.setItem('aisleone_token', data.access_token);
        
        // Clear fields
        uInput.value = '';
        pInput.value = '';
        
        // Verify token and load app
        await checkAuth();
    } catch (err) {
        alert(err.message);
    }
}

function logout() {
    localStorage.removeItem('aisleone_token');
    state.shoppingList = [];
    state.recipeDraftIngredients = [];
    state.selectedRecipe = null;
    renderShoppingList();
    renderRecipeDraft();
    
    // Reset view placeholders
    document.getElementById('results-container').classList.add('hidden');
    document.getElementById('results-placeholder').classList.remove('hidden');
    document.getElementById('recipe-results-container').classList.add('hidden');
    document.getElementById('recipe-results-placeholder').classList.remove('hidden');
    
    checkAuth();
}

// Sync selections back to Database
async function syncProfileWithBackend() {
    const token = localStorage.getItem('aisleone_token');
    if (!token) return;
    
    const payload = {
        tier: state.tier,
        club_memberships: state.clubMemberships,
        zip_code: state.zipCode
    };
    
    try {
        const response = await fetch('/users/profile', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error('Sync failed');
        
        updateUserTierBadge(state.tier);
    } catch (err) {
        console.error('Failed to sync profile preferences:', err);
    }
}

function handleZipKeyPress(event) {
    if (event.key === 'Enter') {
        updateZipCode();
    }
}

async function updateZipCode() {
    const input = document.getElementById('display-zip');
    const zip = input.value.trim();
    if (!zip) return;
    
    state.zipCode = zip;
    await syncProfileWithBackend();
    triggerAutoReoptimize();
}

// Apply Lock Overlays on Frontend
function applyTierRestrictions() {
    const isPremium = state.tier === 'premium';
    const bobRadio = document.getElementById('persona-bob');
    const francineRadio = document.getElementById('persona-francine');
    const bobCard = document.getElementById('card-bob');
    const francineCard = document.getElementById('card-francine');
    const premiumFeatures = document.getElementById('premium-features');

    if (isPremium) {
        bobRadio.disabled = false;
        francineRadio.disabled = false;
        bobCard.classList.remove('locked');
        francineCard.classList.remove('locked');
        premiumFeatures.classList.remove('hidden');
    } else {
        bobRadio.disabled = true;
        francineRadio.disabled = true;
        bobRadio.checked = false;
        francineRadio.checked = false;
        document.getElementById('persona-sam').checked = true;
        state.shopperPersona = 'single_store_sam';
        
        bobCard.classList.add('locked');
        francineCard.classList.add('locked');
        premiumFeatures.classList.add('hidden');
    }
}

// Global Config Functions (Change Trigger Hooks)
async function toggleTier() {
    const isPremium = document.getElementById('tier-premium').checked;
    state.tier = isPremium ? 'premium' : 'free';
    
    if (state.tier === 'free') {
        state.clubMemberships = [];
        document.getElementById('club-costco').checked = false;
        document.getElementById('club-sams').checked = false;
        document.getElementById('club-bjs').checked = false;
    }
    
    applyTierRestrictions();
    
    // Save to Database
    await syncProfileWithBackend();
    
    // Auto re-trigger optimizations if result sheets are open
    triggerAutoReoptimize();
}

async function updateClubs() {
    state.clubMemberships = [];
    if (document.getElementById('club-costco').checked) state.clubMemberships.push('Costco');
    if (document.getElementById('club-sams').checked) state.clubMemberships.push('Sams Club');
    if (document.getElementById('club-bjs').checked) state.clubMemberships.push("BJ's");
    
    // Save to Database
    await syncProfileWithBackend();
    
    // Auto re-trigger optimizations if result sheets are open
    triggerAutoReoptimize();
}

function triggerAutoReoptimize() {
    if (state.shoppingList.length > 0 && !document.getElementById('results-container').classList.contains('hidden')) {
        optimizeList();
    }
    if (state.selectedRecipe) {
        estimateRecipeCostAPI(state.selectedRecipe);
    }
}

// Tab Navigation
function switchTab(tabId) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    
    document.getElementById(`tab-${tabId}`).classList.add('active');
    document.getElementById(`nav-${tabId}`).classList.add('active');
    
    if (tabId === 'recipes') {
        loadRecipes();
    }
}

// Shopping List Builder Functions
let selectedVariantId = null;

async function handleItemInput(event) {
    const q = event.target.value.trim();
    const dropdown = document.getElementById('autocomplete-list');
    if (q.length < 2) {
        dropdown.classList.add('hidden');
        return;
    }
    
    const token = localStorage.getItem('aisleone_token');
    try {
        const response = await fetch(`/search?q=${encodeURIComponent(q)}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        if (!response.ok) return;
        const results = await response.json();
        
        if (results.length === 0) {
            dropdown.classList.add('hidden');
            return;
        }
        
        dropdown.innerHTML = '';
        const uniqueVariants = [];
        const seenNames = new Set();
        
        results.forEach(item => {
            if (!seenNames.has(item.raw_name)) {
                seenNames.add(item.raw_name);
                uniqueVariants.push(item);
            }
        });
        
        uniqueVariants.slice(0, 5).forEach(item => {
            const div = document.createElement('div');
            div.className = 'autocomplete-item';
            div.innerHTML = `
                <span>${item.raw_name}</span>
                <span class="autocomplete-store-badge">${item.store_name} ($${item.price.toFixed(2)})</span>
            `;
            div.onclick = () => selectAutocompleteItem(item);
            dropdown.appendChild(div);
        });
        
        dropdown.classList.remove('hidden');
    } catch (err) {
        console.error('Autocomplete error:', err);
    }
}

function selectAutocompleteItem(item) {
    const input = document.getElementById('item-input');
    input.value = item.raw_name;
    selectedVariantId = item.variant_id || null;
    document.getElementById('autocomplete-list').classList.add('hidden');
    addItemFromInput();
}

function handleItemKeyPress(event) {
    if (event.key === 'Enter') {
        addItemFromInput();
    }
}

function addItemFromInput() {
    const input = document.getElementById('item-input');
    const name = input.value.trim();
    if (!name) return;

    const variantId = selectedVariantId;
    selectedVariantId = null; // reset

    // Prevent duplicate entries
    const duplicate = state.shoppingList.some(item => 
        typeof item === 'object' ? item.name.toLowerCase() === name.toLowerCase() : item.toLowerCase() === name.toLowerCase()
    );

    if (!duplicate) {
        state.shoppingList.push({
            name: name,
            variant_id: variantId
        });
    }

    input.value = '';
    const dropdown = document.getElementById('autocomplete-list');
    if (dropdown) dropdown.classList.add('hidden');

    renderShoppingList();
    triggerAutoReoptimize();
}

function removeItem(index) {
    state.shoppingList.splice(index, 1);
    renderShoppingList();
    triggerAutoReoptimize();
}

// Close autocomplete dropdown when clicking outside
document.addEventListener('click', (event) => {
    const dropdown = document.getElementById('autocomplete-list');
    const input = document.getElementById('item-input');
    if (dropdown && event.target !== dropdown && event.target !== input) {
        dropdown.classList.add('hidden');
    }
});

function renderShoppingList() {
    const listEl = document.getElementById('shopping-list');
    listEl.innerHTML = '';
    
    state.shoppingList.forEach((item, index) => {
        const li = document.createElement('li');
        li.className = 'shopping-item';
        
        const displayName = typeof item === 'object' ? item.name : item;
        const isVariant = typeof item === 'object' && item.variant_id !== null;
        
        li.innerHTML = `
            <span style="display: flex; align-items: center; gap: 0.5rem;">
                ${displayName}
                ${isVariant ? '<span class="badge badge-premium" style="font-size: 0.65rem; padding: 0.1rem 0.35rem;">Brand Locked</span>' : ''}
            </span>
            <span class="delete-btn" onclick="removeItem(${index})">&times;</span>
        `;
        listEl.appendChild(li);
    });
}

// Core List Optimization call
async function optimizeList() {
    const token = localStorage.getItem('aisleone_token');
    if (!token) return;

    if (state.shoppingList.length === 0) {
        alert('Please add some items to your shopping list first.');
        return;
    }

    const personaRadios = document.getElementsByName('persona');
    for (let r of personaRadios) {
        if (r.checked) {
            state.shopperPersona = r.value;
            break;
        }
    }

    // Keep payload simple, backend secures and overwrites tier/clubs from JWT
    const payload = {
        items: state.shoppingList,
        shopper_persona: state.shopperPersona
    };

    try {
        const response = await fetch('/cheapest', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('API request failed');

        const data = await response.json();
        renderListResults(data);
    } catch (err) {
        console.error(err);
        alert('Error matching items. Make sure backend is running.');
    }
}

function renderListResults(data) {
    document.getElementById('results-placeholder').classList.add('hidden');
    document.getElementById('results-container').classList.remove('hidden');

    document.getElementById('metric-total').innerText = `$${(data.total_cost || 0).toFixed(2)}`;
    document.getElementById('metric-stores').innerText = data.num_stores || data.stores_used.length;
    
    const modeEl = document.getElementById('metric-mode');
    modeEl.innerText = data.mode === 'single_store' ? 'Sam (Single)' : data.mode === 'minimize_visits' ? 'Bob (Balanced)' : 'Francine (Frugal)';
    modeEl.className = `metric-value badge ${data.mode === 'single_store' ? 'badge-free' : 'badge-premium'}`;

    const tbody = document.getElementById('results-table-body');
    tbody.innerHTML = '';

    data.items.forEach(item => {
        const tr = document.createElement('tr');
        const priceText = item.price !== null ? `$${item.price.toFixed(2)}` : 'N/A';
        const storeText = item.store ? `<span class="store-badge">${item.store}</span>` : `<span class="store-badge" style="color: var(--danger)">Unavailable</span>`;
        
        tr.innerHTML = `
            <td><strong>${item.query}</strong></td>
            <td><span style="color: var(--text-muted)">${item.canonical || 'No match'}</span></td>
            <td>${storeText}</td>
            <td class="text-right">${priceText}</td>
        `;
        tbody.appendChild(tr);
    });

    const subtotalList = document.getElementById('store-breakdown-list');
    subtotalList.innerHTML = '';

    if (data.store_totals) {
        Object.entries(data.store_totals).forEach(([store, amount]) => {
            const card = document.createElement('div');
            card.className = 'store-spend-card';
            card.innerHTML = `
                <span class="store-spend-name">${store}</span>
                <span class="store-spend-amount">$${amount.toFixed(2)}</span>
            `;
            subtotalList.appendChild(card);
        });
    } else if (data.selected_store && data.total_cost) {
        const card = document.createElement('div');
        card.className = 'store-spend-card';
        card.innerHTML = `
            <span class="store-spend-name">${data.selected_store}</span>
            <span class="store-spend-amount">$${data.total_cost.toFixed(2)}</span>
        `;
        subtotalList.appendChild(card);
    }

    // Generate Grouped Store Checklists
    const checklistsContainer = document.getElementById('shopping-checklists-container');
    checklistsContainer.innerHTML = '';
    
    // Group items by store
    const storeGroups = {};
    data.items.forEach(item => {
        const storeName = item.store || 'Unavailable';
        if (!storeGroups[storeName]) {
            storeGroups[storeName] = [];
        }
        storeGroups[storeName].push(item);
    });
    
    Object.entries(storeGroups).forEach(([store, items]) => {
        const card = document.createElement('div');
        card.className = 'store-checklist-card';
        
        let itemsHtml = '';
        items.forEach(item => {
            const itemPriceText = item.price !== null ? `$${item.price.toFixed(2)}` : 'N/A';
            const displayName = item.raw_name || item.canonical || item.query;
            itemsHtml += `
                <li class="checklist-item">
                    <input type="checkbox">
                    <span>${displayName} (${itemPriceText})</span>
                </li>
            `;
        });
        
        const storeTotal = items.reduce((sum, item) => sum + (item.price || 0), 0);
        card.innerHTML = `
            <h5>
                <span>🏪 ${store}</span>
                <span class="store-checklist-total">$${storeTotal.toFixed(2)}</span>
            </h5>
            <ul>
                ${itemsHtml}
            </ul>
        `;
        checklistsContainer.appendChild(card);
    });
}

// Recipes tab calls
async function loadRecipes() {
    const token = localStorage.getItem('aisleone_token');
    if (!token) return;

    try {
        const response = await fetch('/recipes', {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        if (!response.ok) throw new Error('Failed to load recipes');
        state.recipes = await response.json();
        renderRecipesList();
    } catch (err) {
        console.error(err);
    }
}

function renderRecipesList() {
    const listEl = document.getElementById('recipe-list');
    listEl.innerHTML = '';

    state.recipes.forEach(recipe => {
        const li = document.createElement('li');
        li.className = `recipe-item ${state.selectedRecipe && state.selectedRecipe.name === recipe.name ? 'active' : ''}`;
        li.innerHTML = `
            <span>${recipe.name}</span>
            <span style="font-size: 0.8rem; color: var(--text-muted);">${recipe.ingredients.length} items</span>
        `;
        li.onclick = () => selectRecipe(recipe);
        listEl.appendChild(li);
    });
}

function selectRecipe(recipe) {
    state.selectedRecipe = recipe;
    renderRecipesList();
    estimateRecipeCostAPI(recipe);
}

async function estimateRecipeCostAPI(recipe) {
    const token = localStorage.getItem('aisleone_token');
    if (!token) return;

    const personaRadios = document.getElementsByName('persona');
    for (let r of personaRadios) {
        if (r.checked) {
            state.shopperPersona = r.value;
            break;
        }
    }

    const payload = {
        name: recipe.name,
        ingredients: recipe.ingredients,
        shopper_persona: state.shopperPersona
    };

    try {
        const response = await fetch('/recipes/estimate', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('API call failed');
        const data = await response.json();
        renderRecipeEstimate(data);
    } catch (err) {
        console.error(err);
        alert('Error fetching recipe pricing');
    }
}

function renderRecipeEstimate(data) {
    document.getElementById('recipe-results-placeholder').classList.add('hidden');
    document.getElementById('recipe-results-container').classList.remove('hidden');

    document.getElementById('recipe-result-title').innerText = data.recipe_name;
    document.getElementById('recipe-result-mode').innerText = data.mode === 'single_store' ? 'Sam (Single)' : data.mode === 'minimize_visits' ? 'Bob (Balanced)' : 'Francine (Frugal)';
    
    document.getElementById('recipe-metric-total').innerText = `$${(data.estimated_total || 0).toFixed(2)}`;
    document.getElementById('recipe-metric-stores').innerText = data.stores_used.length;
    document.getElementById('recipe-metric-main-store').innerText = data.selected_store || 'Multiple';

    const tbody = document.getElementById('recipe-results-table-body');
    tbody.innerHTML = '';

    data.ingredients.forEach(item => {
        const tr = document.createElement('tr');
        const priceText = item.price !== null ? `$${item.price.toFixed(2)}` : 'N/A';
        const storeText = item.store ? `<span class="store-badge">${item.store}</span>` : `<span class="store-badge" style="color: var(--danger)">Unavailable</span>`;
        const qtyText = `${item.quantity || 1.0} ${item.unit || ''}`.trim();
        
        tr.innerHTML = `
            <td><strong>${item.name}</strong><br><small style="color: var(--text-muted)">${item.raw_name || ''}</small></td>
            <td>${qtyText}</td>
            <td>${storeText}</td>
            <td class="text-right">${priceText}</td>
        `;
        tbody.appendChild(tr);
    });

    const missingBox = document.getElementById('recipe-missing-box');
    const missingList = document.getElementById('recipe-missing-list');
    missingList.innerHTML = '';
    
    if (data.missing_ingredients && data.missing_ingredients.length > 0) {
        missingBox.classList.remove('hidden');
        data.missing_ingredients.forEach(m => {
            const li = document.createElement('li');
            li.innerText = `${m.name} - ${m.reason}`;
            missingList.appendChild(li);
        });
    } else {
        missingBox.classList.add('hidden');
    }
}

// Recipe Form Actions
function addIngredientToDraft() {
    const nameInput = document.getElementById('ing-name');
    const qtyInput = document.getElementById('ing-qty');
    const unitInput = document.getElementById('ing-unit');

    const name = nameInput.value.trim();
    const qty = parseFloat(qtyInput.value) || 1.0;
    const unit = unitInput.value.trim() || null;

    if (!name) return;

    state.recipeDraftIngredients.push({ name, quantity: qty, unit });
    
    nameInput.value = '';
    qtyInput.value = '1';
    unitInput.value = '';

    renderRecipeDraft();
}

function renderRecipeDraft() {
    const listEl = document.getElementById('recipe-draft-ingredients');
    listEl.innerHTML = '';

    state.recipeDraftIngredients.forEach((ing, index) => {
        const li = document.createElement('li');
        li.className = 'recipe-draft-item';
        li.innerHTML = `
            <span>${ing.name} (${ing.quantity} ${ing.unit || ''})</span>
            <span style="cursor:pointer; color: var(--danger)" onclick="removeDraftIng(${index})">Remove</span>
        `;
        listEl.appendChild(li);
    });
}

function removeDraftIng(index) {
    state.recipeDraftIngredients.splice(index, 1);
    renderRecipeDraft();
}

async function saveRecipe() {
    const token = localStorage.getItem('aisleone_token');
    if (!token) return;

    const nameInput = document.getElementById('recipe-name-input');
    const name = nameInput.value.trim();

    if (!name) {
        alert('Please enter a recipe name.');
        return;
    }
    if (state.recipeDraftIngredients.length === 0) {
        alert('Please add at least one ingredient to the recipe.');
        return;
    }

    const payload = {
        name,
        ingredients: state.recipeDraftIngredients
    };

    try {
        const response = await fetch('/recipes', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('Failed to save recipe');

        nameInput.value = '';
        state.recipeDraftIngredients = [];
        renderRecipeDraft();
        await loadRecipes();
        alert('Recipe saved successfully!');
    } catch (err) {
        console.error(err);
        alert('Error saving recipe');
    }
}

// Price Explorer Actions
function handleExplorerSearchPress(event) {
    if (event.key === 'Enter') {
        searchExplorer();
    }
}

async function searchExplorer() {
    const token = localStorage.getItem('aisleone_token');
    if (!token) return;

    const input = document.getElementById('explorer-search');
    const q = input.value.trim();
    if (!q) return;

    try {
        const response = await fetch(`/search?q=${encodeURIComponent(q)}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        if (!response.ok) throw new Error('Search failed');

        const rows = await response.json();
        renderExplorerResults(rows);
    } catch (err) {
        console.error(err);
        alert('Explorer search failed');
    }
}

function renderExplorerResults(rows) {
    const container = document.getElementById('explorer-results');
    container.innerHTML = '';

    if (rows.length === 0) {
        container.innerHTML = `
            <div class="results-placeholder" style="grid-column: 1/-1;">
                <span class="placeholder-icon">🍿</span>
                <p>No products or variants found matching your search.</p>
            </div>
        `;
        return;
    }

    const grouped = {};
    rows.forEach(row => {
        const key = row.canonical_name;
        if (!grouped[key]) grouped[key] = [];
        grouped[key].push(row);
    });

    Object.entries(grouped).forEach(([canonicalName, prices]) => {
        const card = document.createElement('div');
        card.className = 'explorer-card';
        
        let pricesHtml = '';
        prices.forEach(p => {
            const clubClass = p.is_club ? 'class="club-store"' : '';
            const clubIndicator = p.is_club ? ' <span style="font-size: 0.7rem; color: var(--premium)">[Club]</span>' : '';
            pricesHtml += `
                <div ${clubClass} class="explorer-store-row">
                    <span class="store-name">${p.store_name}${clubIndicator}<br><small style="color: var(--text-muted)">${p.raw_name}</small></span>
                    <span class="store-price">$${p.price.toFixed(2)}</span>
                </div>
            `;
        });

        card.innerHTML = `
            <h4 style="text-transform: capitalize;">${canonicalName}</h4>
            <div class="explorer-prices-list">
                ${pricesHtml}
            </div>
        `;
        container.appendChild(card);
    });
}

// Bulk Import Modal controls and text parser
function openImportModal() {
    document.getElementById('import-textarea').value = '';
    document.getElementById('import-modal').classList.remove('hidden');
}

function closeImportModal() {
    document.getElementById('import-modal').classList.add('hidden');
}

function parseAndImportBulkText() {
    const text = document.getElementById('import-textarea').value.trim();
    if (!text) {
        closeImportModal();
        return;
    }
    
    // Split by newlines, commas, or semicolons
    const lines = text.split(/[\n,;]+/);
    let addedCount = 0;
    
    lines.forEach(line => {
        let clean = line.trim();
        if (!clean) return;
        
        // Strip out bullet list and numbered formatting indicators
        clean = clean.replace(/^[-\*••+\s]+/, '');
        clean = clean.replace(/^\[?\d+\]?[\.\)\s:-]*/, '');
        clean = clean.trim();
        
        if (!clean) return;
        
        // Deduplicate items on addition
        const duplicate = state.shoppingList.some(item => 
            typeof item === 'object' ? item.name.toLowerCase() === clean.toLowerCase() : item.toLowerCase() === clean.toLowerCase()
        );
        
        if (!duplicate) {
            state.shoppingList.push({
                name: clean,
                variant_id: null
            });
            addedCount++;
        }
    });
    
    closeImportModal();
    if (addedCount > 0) {
        renderShoppingList();
        triggerAutoReoptimize();
    }
}

// Recipe to active shopping list merge utility
function addRecipeToShoppingList() {
    if (!state.selectedRecipe) return;
    
    let addedCount = 0;
    state.selectedRecipe.ingredients.forEach(ing => {
        const name = ing.name.trim();
        if (!name) return;
        
        const duplicate = state.shoppingList.some(item => 
            typeof item === 'object' ? item.name.toLowerCase() === name.toLowerCase() : item.toLowerCase() === name.toLowerCase()
        );
        
        if (!duplicate) {
            state.shoppingList.push({
                name: name,
                variant_id: null
            });
            addedCount++;
        }
    });
    
    if (addedCount > 0) {
        renderShoppingList();
        triggerAutoReoptimize();
        switchTab('list');
    } else {
        alert('All recipe ingredients are already in your active shopping list!');
    }
}
