document.addEventListener('DOMContentLoaded', () => {
    const runButton = document.getElementById('run-button');
    const statusMessage = document.getElementById('status-message');
    const resultsContainer = document.getElementById('results-table-container');

    // --- Elements for Parameters ---
    const minCoverageInput = document.getElementById('min-coverage');
    const minSkusInput = document.getElementById('min-skus');
    const restrictedBrandsInput = document.getElementById('restricted-brands');
    const jwtTokenInput = document.getElementById('jwt-token'); // Added JWT input

    // --- Elements for Data Display / Input ---
    const productsDataEl = document.getElementById('products-data'); // Still display only
    const channelsDataEl = document.getElementById('channels-data'); // Still display only
    const inventoryDataEl = document.getElementById('inventory-data'); // Still display only
    const demandDataTextArea = document.getElementById('demand-data'); // Changed to textarea
    // const revenueDataTextArea = document.getElementById('revenue-data'); // Removed revenue textarea reference

    // --- Load initial/sample display data (Products, Channels, Inventory) ---
    // Hardcoded simple examples for display context
    productsDataEl.textContent = JSON.stringify([
        { sku: 'SKU001', donation_eligible: true, brand: 'BrandA' },
        { sku: 'SKU002', donation_eligible: false, brand: 'BrandA' },
        { sku: 'SKU003', donation_eligible: true, brand: 'BrandB' }
    ], null, 2); // Pretty print JSON
    channelsDataEl.textContent = JSON.stringify([
        { id: 'STORE1', capacity: 100, min_coverage: 0.5, channel_type: 'store' },
        { id: 'OUTLET1', capacity: 200, min_coverage: 0.0, channel_type: 'outlet' },
        { id: 'DONATE1', capacity: 50, min_coverage: 0.0, channel_type: 'donation' }
    ], null, 2);
    inventoryDataEl.textContent = JSON.stringify([
        { product_sku: 'SKU001', quantity: 70 },
        { product_sku: 'SKU002', quantity: 30 },
        { product_sku: 'SKU003', quantity: 40 }
    ], null, 2);
    // Demand and Revenue are inputs

    // --- Event Listener for Run Button ---
    runButton.addEventListener('click', async () => {
        statusMessage.textContent = 'Running allocation...';
        statusMessage.style.color = 'orange';
        resultsContainer.innerHTML = '<p>Processing...</p>'; // Clear previous results

        // --- Get Parameters from Inputs ---
        const defaultMinCoverage = minCoverageInput.value ? parseFloat(minCoverageInput.value) : null;
        const minSkusPerStore = minSkusInput.value ? parseInt(minSkusInput.value, 10) : null;
        const restrictedBrands = restrictedBrandsInput.value
            ? restrictedBrandsInput.value.split(',').map(brand => brand.trim()).filter(brand => brand) // Split, trim, remove empty
            : null;

        const parameters = {
            default_min_coverage: defaultMinCoverage,
            min_skus_per_store: minSkusPerStore,
            restricted_brands_for_donation: restrictedBrands
        };

        // --- Get and Parse Demand Data from TextArea ---
        let demandData = {};
        // let revenueData = {}; // Removed revenue data variable
        let parseError = false;

        try {
            const demandJson = demandDataTextArea.value.trim();
            if (demandJson) {
                demandData = JSON.parse(demandJson);
            } else {
                 statusMessage.textContent = 'Warning: Demand data is empty.';
                 statusMessage.style.color = 'darkorange'; // Use a different color for warnings
            }
        } catch (e) {
            statusMessage.textContent = 'Error: Invalid JSON in Demand Data field.';
            statusMessage.style.color = 'red';
            parseError = true;
        }

        // Removed revenue parsing block

        // Stop if there was a JSON parsing error
        if (parseError) {
            resultsContainer.innerHTML = '<p>Correct JSON errors before running.</p>';
            return;
        }


        // --- Prepare API Request Body ---
        const requestBody = {
            demand: demandData,
            // revenue: revenueData, // Removed revenue from request
            parameters: parameters
        };

        // --- Call Backend API ---
        try {
            // --- Get Auth Token ---
            const authToken = jwtTokenInput.value.trim();
            if (!authToken) {
                statusMessage.textContent = 'Error: JWT Token is required.';
                statusMessage.style.color = 'red';
                resultsContainer.innerHTML = '<p>Please provide a JWT token.</p>';
                return; // Stop if no token
            }

            const response = await fetch('/api/inventory/allocate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}` // Add JWT token
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(`API Error (${response.status}): ${errorData.error || 'Unknown error'}`);
            }

            const allocationResults = await response.json();

            // --- Display Results ---
            statusMessage.textContent = 'Allocation successful!';
            statusMessage.style.color = 'green';
            renderResultsTable(allocationResults);

        } catch (error) {
            console.error('Allocation failed:', error);
            statusMessage.textContent = `Error: ${error.message}`;
            statusMessage.style.color = 'red';
            resultsContainer.innerHTML = '<p>Failed to get allocation results.</p>';
        }
    });

    // --- Function to Render Results Table ---
    function renderResultsTable(results) {
        if (!results || results.length === 0) {
            resultsContainer.innerHTML = '<p>No allocation results generated.</p>';
            return;
        }

        let tableHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Product SKU</th>
                        <th>Channel ID</th>
                        <th>Allocated Quantity</th>
                        <!-- Removed Estimated Revenue Header -->
                    </tr>
                </thead>
                <tbody>
        `;

        results.forEach(alloc => {
            tableHTML += `
                <tr>
                    <td>${alloc.product_sku}</td>
                    <td>${alloc.channel_id}</td>
                    <td>${alloc.quantity}</td>
                    <!-- Removed Estimated Revenue Cell -->
                </tr>
            `;
        });

        tableHTML += `
                </tbody>
            </table>
        `;

        resultsContainer.innerHTML = tableHTML;
    }
});
