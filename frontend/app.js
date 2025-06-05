document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const summaryView = document.getElementById('summary-view');
    const detailedView = document.getElementById('detailed-view');
    const allocationToolForm = document.getElementById('allocation-tool-form');

    // Navigation buttons
    const editAllocationBtn = document.getElementById('edit-allocation-btn');
    const backToSummaryBtn = document.getElementById('back-to-summary');
    const runButton = document.getElementById('run-button'); // Keep for original form section if used
    const saveAllocationBtn = document.getElementById('save-allocation');
    const autoAllocateBtn = document.getElementById('auto-allocate');
    const validateAllocationBtn = document.getElementById('validate-allocation-btn');

    // Export buttons
    const exportExcelBtn = document.getElementById('export-excel');
    const exportDetailExcelBtn = document.getElementById('export-detail-excel');

    // Theme toggle
    const themeToggleBtn = document.getElementById('theme-toggle');

    // Filter elements
    const divisionFilterSummary = document.getElementById('division-filter-summary');
    const brandFilterSummary = document.getElementById('brand-filter-summary');
    const categoryFilterSummary = document.getElementById('category-filter-summary');
    const divisionFilterDetail = document.getElementById('division-filter-detail');
    const brandFilterDetail = document.getElementById('brand-filter-detail');
    const categoryFilterDetail = document.getElementById('category-filter-detail');
    const plantFilterSummary = document.getElementById('plant-filter-summary'); // New
    const plantFilterDetail = document.getElementById('plant-filter-detail'); // New

    // Metric toggles
    const unitToggle = document.getElementById('unit-toggle');
    const cogToggle = document.getElementById('cog-toggle');

    // Date filter (Modal functionality removed/simplified)
    const currentDateEl = document.getElementById('current-date');
    // const dateModal = document.getElementById('date-modal'); // Assuming modal elements might not exist or are hidden
    // const closeModalBtn = document.querySelector('.close-modal');
    // const cancelDateBtn = document.getElementById('cancel-date');
    // const applyDateBtn = document.getElementById('apply-date');

    // Validation elements
    const validationErrors = document.getElementById('validation-errors');
    const errorMessage = document.getElementById('error-message');

    // Metrics elements
    const totalUnitsEl = document.getElementById('total-units');
    const totalCogsEl = document.getElementById('total-cogs');
    const detailTotalUnitsEl = document.getElementById('detail-total-units');
    const detailTotalSkusEl = document.getElementById('detail-total-skus');
    const allocationStatusEl = document.getElementById('allocation-status');

    // Table and chart containers
    const allocationTable = document.getElementById('allocation-table');
    const allocationChartContainer = document.getElementById('allocation-chart');
    const divisionChartContainer = document.getElementById('division-chart');
    const brandChartContainer = document.getElementById('brand-chart');
    const allocationLegend = document.getElementById('allocation-legend');

    // Original tool elements (if still present in HTML)
    const statusMessage = document.getElementById('status-message');
    const productsDataEl = document.getElementById('products-data');
    const channelsDataEl = document.getElementById('channels-data');
    const inventoryDataEl = document.getElementById('inventory-data');
    const demandDataTextArea = document.getElementById('demand-data');

    // --- Application State ---
    let currentTheme = localStorage.getItem('theme') || 'light';
    let currentMetricView = 'unit'; // 'unit' or 'cog'
    let currentDate = { month: 'JANUARY', year: 2024 }; // Keep default or fetch from backend?
    let currentSortColumn = null;
    let currentSortDirection = 'asc';
    let allocationData = []; // Will be populated by API
    let channelColumns = []; // Will be populated by API
    let currentAllocationStatus = 'UNKNOWN'; // Renamed from allocationStatus for clarity

    // --- Initialize Application ---
    function initializeApp() {
        // Apply saved theme
        document.documentElement.setAttribute('data-theme', currentTheme);
        updateThemeToggleIcon();

        // Ensure modal is hidden initially (if it exists)
        // if (dateModal) dateModal.classList.add('hidden');

        // Initialize original tool data display (if elements exist)
        // These might be removed if the old form section is gone
        if (productsDataEl) productsDataEl.textContent = '{}'; // Clear sample data
        if (channelsDataEl) channelsDataEl.textContent = '{}';
        if (inventoryDataEl) inventoryDataEl.textContent = '{}';

        // Fetch allocation data from backend
        fetchAllocationData(); // This will now call the API

        // Show summary view by default
        summaryView.classList.remove('hidden');
        detailedView.classList.add('hidden');
        if (allocationToolForm) allocationToolForm.classList.add('hidden'); // Hide old form if exists

        // Setup event listeners
        setupEventListeners();
    }

    // --- Setup Event Listeners ---
    function setupEventListeners() {
        // Navigation between views
        editAllocationBtn.addEventListener('click', () => {
            summaryView.classList.add('hidden');
            detailedView.classList.remove('hidden');
            if (allocationToolForm) allocationToolForm.classList.add('hidden');
            renderAllocationTable(); // Re-render table when switching to detail view
        });

        backToSummaryBtn.addEventListener('click', () => {
            summaryView.classList.remove('hidden');
            detailedView.classList.add('hidden');
            if (allocationToolForm) allocationToolForm.classList.add('hidden');
            // No need to re-render table, summary charts/metrics updated by fetch or filters
        });

        // Theme toggle
        themeToggleBtn.addEventListener('click', toggleTheme);

        // Metric toggles
        unitToggle.addEventListener('click', () => {
            currentMetricView = 'unit';
            unitToggle.classList.add('active');
            cogToggle.classList.remove('active');
            updateSummaryMetrics(); // Update summary metrics based on new view
            renderAllocationChart(); // Re-render charts based on new view
            renderDivisionChart();
            renderBrandChart();
            renderAllocationLegend();
        });

        cogToggle.addEventListener('click', () => {
            currentMetricView = 'cog';
            cogToggle.classList.add('active');
            unitToggle.classList.remove('active');
            updateSummaryMetrics(); // Update summary metrics based on new view
            renderAllocationChart(); // Re-render charts based on new view
            renderDivisionChart();
            renderBrandChart();
            renderAllocationLegend();
        });

        // Date filter - simplified/removed modal functionality
        if (currentDateEl && currentDateEl.parentElement) {
            currentDateEl.parentElement.addEventListener('click', () => {
                alert('Date selection is not implemented in this version.');
            });
        }
        // Remove modal listeners if modal is gone
        // if (closeModalBtn) closeModalBtn.addEventListener('click', () => dateModal.classList.add('hidden'));
        // if (cancelDateBtn) cancelDateBtn.addEventListener('click', () => dateModal.classList.add('hidden'));
        // if (applyDateBtn) applyDateBtn.addEventListener('click', applyDateChange);
        // document.addEventListener('click', (event) => { if (dateModal && event.target === dateModal) dateModal.classList.add('hidden'); });

        // Export buttons
        exportExcelBtn.addEventListener('click', () => exportToExcel('allocation_summary'));
        exportDetailExcelBtn.addEventListener('click', () => exportToExcel('allocation_details'));

        // Action buttons
        saveAllocationBtn.addEventListener('click', saveAllocation);
        autoAllocateBtn.addEventListener('click', autoAllocate);
        validateAllocationBtn.addEventListener('click', validateAllocation);
        if (runButton) runButton.addEventListener('click', runAllocation); // Keep if old form exists

        // Filter change handlers
        [divisionFilterSummary, brandFilterSummary, categoryFilterSummary, plantFilterSummary].forEach(filter => {
            if (filter) { // Add null check
                filter.addEventListener('change', () => {
                    const filtered = filterData(); // Apply filters first
                    renderAllocationChart(filtered); // Pass filtered data to render functions
                    renderDivisionChart(filtered);
                    renderBrandChart(filtered);
                    updateSummaryMetrics(filtered);
                    renderAllocationLegend(filtered);
                });
            }
        });

        [divisionFilterDetail, brandFilterDetail, categoryFilterDetail, plantFilterDetail].forEach(filter => {
            if (filter) { // Add null check
                filter.addEventListener('change', () => {
                    renderAllocationTable(); // Re-render table with new filters applied
                });
            }
        });
    }

    // --- Theme Functions ---
    function toggleTheme() {
        currentTheme = currentTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', currentTheme);
        localStorage.setItem('theme', currentTheme);
        updateThemeToggleIcon();
        // Re-render charts as theme changes might affect colors
        const filtered = filterData();
        renderAllocationChart(filtered);
        renderDivisionChart(filtered);
        renderBrandChart(filtered);
    }

    function updateThemeToggleIcon() {
        const icon = themeToggleBtn.querySelector('i');
        if (currentTheme === 'dark') {
            icon.className = 'fas fa-sun';
        } else {
            icon.className = 'fas fa-moon';
        }
    }

    // --- Data Functions ---
    async function fetchAllocationData() {
        if(statusMessage) {
            statusMessage.textContent = 'Loading allocation data...';
            statusMessage.style.color = 'orange';
        }

        try {
            const response = await fetch('http://127.0.0.1:5000/api/allocation_data'); // TODO: Add auth headers if needed

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Failed to parse error response' }));
                throw new Error(`HTTP error! status: ${response.status} - ${errorData.error || response.statusText}`);
            }

            const data = await response.json();

            // Update state with fetched data
            allocationData = data.allocationData || [];
            channelColumns = data.channelColumns || [];
            const apiStatus = data.allocationStatus || 'UNKNOWN'; // Get status from API

            // Initial render/update of UI components
            populateFilters();
            const filtered = filterData(); // Get initially filtered data
            renderAllocationChart(filtered);
            renderDivisionChart(filtered);
            renderBrandChart(filtered);
            updateSummaryMetrics(filtered);
            renderAllocationLegend(filtered);
            
            if (validationErrors) {
                validationErrors.classList.add('hidden'); 
                console.log('fetchAllocationData: validationErrors explicitly hidden before table render.'); // LOGGING
            }
            renderAllocationTable(); // Render table with initial data
            if (validationErrors) {
                console.log(`fetchAllocationData: After renderAllocationTable, validationErrors hidden: ${validationErrors.classList.contains('hidden')}`); // LOGGING
            }

            // Determine and set the initial detailed status after rendering
            updateAllocationStatus();

            if(statusMessage) {
                statusMessage.textContent = 'Data loaded successfully.';
                statusMessage.style.color = 'green';
                setTimeout(() => { if(statusMessage) statusMessage.textContent = ''; }, 3000);
            }

        } catch (error) {
            console.error('Error fetching allocation data:', error);
            if(statusMessage) {
                statusMessage.textContent = `Error loading data: ${error.message}`;
                statusMessage.style.color = 'red';
            }
            allocationStatusEl.textContent = 'ERROR';
            allocationStatusEl.style.backgroundColor = 'var(--error-color)';
            // Reset data to avoid errors in rendering functions
            allocationData = [];
            channelColumns = [];
            // Attempt to render empty state
            populateFilters();
            renderAllocationChart([]);
            renderDivisionChart([]);
            renderBrandChart([]);
            updateSummaryMetrics([]);
            renderAllocationLegend([]);
            renderAllocationTable();
            updateAllocationStatus(); // Update status even on error (likely 'ERROR')
        }
    }

    function populateFilters() {
        // Get unique values for filters, handling potential nulls
        const divisions = [...new Set(allocationData.map(item => item.div).filter(Boolean))];
        const brands = [...new Set(allocationData.map(item => item.signature).filter(Boolean))];
        const categories = [...new Set(allocationData.map(item => item.hierarchy).filter(Boolean))];
        const plants = [...new Set(allocationData.map(item => item.plant).filter(Boolean))]; // New

        // Populate division filters
        populateFilterOptions(divisionFilterSummary, divisions);
        populateFilterOptions(divisionFilterDetail, divisions);

        // Populate brand filters
        populateFilterOptions(brandFilterSummary, brands);
        populateFilterOptions(brandFilterDetail, brands);

        // Populate category filters
        populateFilterOptions(categoryFilterSummary, categories);
        populateFilterOptions(categoryFilterDetail, categories);

        // Populate plant filters
        populateFilterOptions(plantFilterSummary, plants);
        populateFilterOptions(plantFilterDetail, plants);
    }

    function populateFilterOptions(selectElement, options) {
        if (!selectElement) return; // Guard against missing elements
        // Keep the first option (All)
        const firstOption = selectElement.options[0];
        selectElement.innerHTML = '';
        if (firstOption) selectElement.appendChild(firstOption); // Add back 'All' if it existed

        // Add new options
        options.sort().forEach(option => { // Sort options alphabetically
            const optionElement = document.createElement('option');
            optionElement.value = option;
            optionElement.textContent = option;
            selectElement.appendChild(optionElement);
        });
    }

    function filterData() {
        // Get filter values from the currently visible view
        const isDetailView = !detailedView.classList.contains('hidden');
        
        const divisionFilterValue = isDetailView ? divisionFilterDetail?.value : divisionFilterSummary?.value;
        const brandFilterValue = isDetailView ? brandFilterDetail?.value : brandFilterSummary?.value;
        const categoryFilterValue = isDetailView ? categoryFilterDetail?.value : categoryFilterSummary?.value;
        const plantFilterValue = isDetailView ? plantFilterDetail?.value : plantFilterSummary?.value; // New

        const divisionFilter = divisionFilterValue || 'all';
        const brandFilter = brandFilterValue || 'all';
        const categoryFilter = categoryFilterValue || 'all';
        const plantFilter = plantFilterValue || 'all'; // New


        // Apply filters
        let filteredData = [...allocationData];

        if (divisionFilter !== 'all') {
            filteredData = filteredData.filter(item => item.div === divisionFilter);
        }

        if (brandFilter !== 'all') {
            filteredData = filteredData.filter(item => item.signature === brandFilter);
        }

        if (categoryFilter !== 'all') {
            filteredData = filteredData.filter(item => item.hierarchy === categoryFilter);
        }

        if (plantFilter !== 'all') { // New
            filteredData = filteredData.filter(item => item.plant === plantFilter);
        }

        return filteredData;
    }

    function sortData(data, column, direction) {
        // Ensure data is an array
         const dataToSort = Array.isArray(data) ? [...data] : [];

        return dataToSort.sort((a, b) => {
            let valueA, valueB;

            // Handle special cases for sorting
            if (column === 'units') { // Ensure units are sorted numerically
                 valueA = a.units || 0;
                 valueB = b.units || 0;
            } else if (column === 'allocAccu') {
                 // Calculate percentage from the item's total units and channel allocations for sorting
                 const totalAllocatedA = Object.values(a.channels || {}).reduce((sum, val) => sum + (val || 0), 0);
                 const totalAllocatedB = Object.values(b.channels || {}).reduce((sum, val) => sum + (val || 0), 0);
                 // Use Math.round for sorting consistency with display
                 valueA = (a.units > 0) ? Math.round((totalAllocatedA / a.units) * 100) : 0;
                 valueB = (b.units > 0) ? Math.round((totalAllocatedB / b.units) * 100) : 0;
            } else if (column === 'remainingQty') { // Added sorting for remainingQty
                 // Calculate remaining quantity for sorting
                 const totalAllocatedA = Object.values(a.channels || {}).reduce((sum, val) => sum + (val || 0), 0);
                 const totalAllocatedB = Object.values(b.channels || {}).reduce((sum, val) => sum + (val || 0), 0);
                 valueA = (a.units || 0) - totalAllocatedA;
                 valueB = (b.units || 0) - totalAllocatedB;
            } else if (column.startsWith('channels.')) {
                const channelName = column.split('.')[1];
                valueA = a.channels?.[channelName] || 0;
                valueB = b.channels?.[channelName] || 0;
            } else {
                valueA = a[column];
                valueB = b[column];
            }

            // Sort based on data type
            if (typeof valueA === 'number' && typeof valueB === 'number') {
                return direction === 'asc' ? valueA - valueB : valueB - valueA;
            } else {
                // Ensure values are strings for localeCompare, handle null/undefined
                valueA = valueA?.toString() ?? '';
                valueB = valueB?.toString() ?? '';
                return direction === 'asc' ? valueA.localeCompare(valueB) : valueB.localeCompare(valueA);
            }
        });
    }

    // --- Render Functions ---
    function renderAllocationTable() {
        if (!allocationTable) return; // Exit if table element doesn't exist

        let dataToRender = filterData(); // Apply filters

        // Apply sorting if set
        if (currentSortColumn) {
            dataToRender = sortData(dataToRender, currentSortColumn, currentSortDirection);
        }

        const tableHeader = allocationTable.querySelector('thead tr');
        const tableBody = allocationTable.querySelector('tbody');

        if (!tableHeader || !tableBody) return; // Exit if header/body elements missing

        // --- Update table header ---
        // Clear existing dynamic channel columns AND remove old listeners from static ones
        const staticHeaders = tableHeader.querySelectorAll('th');
        staticHeaders.forEach((th, index) => {
             // Remove old listener before adding new one (important if re-rendering)
             th.replaceWith(th.cloneNode(true)); // Simple way to remove all listeners
        });
        const updatedStaticHeaders = tableHeader.querySelectorAll('th'); // Re-select after cloning

        // Define static columns and their corresponding data keys
        const staticColumnDefs = [
            { headerText: 'Div', key: 'div' },
            { headerText: 'Signature', key: 'signature' },
            { headerText: 'Axe', key: 'axe' },
            { headerText: 'SubAxe', key: 'subAxe' },
            { headerText: 'Metier', key: 'metier' },
            { headerText: 'EAN', key: 'ean' },
            { headerText: 'SKU', key: 'sku' },
            { headerText: 'Description', key: 'description' },
            { headerText: 'Units', key: 'units' },
            { headerText: 'Plant', key: 'plant' }, // Changed from 'Stock origin', data key is 'plant' (which holds description)
            { headerText: 'FlagExcess6months', key: 'flagExcess6months' },
            { headerText: 'FlagExcess12months', key: 'flagExcess12months' },
            { headerText: 'Allocation %', key: 'allocAccu' },
            { headerText: 'Remaining Qty', key: 'remainingQty' }
        ];

        // Add sort listeners to static headers
        updatedStaticHeaders.forEach((th, index) => {
            if (index < staticColumnDefs.length) { // Only for defined static columns
                 const def = staticColumnDefs[index];
                 th.classList.add('sortable'); // Ensure class is present
                 th.innerHTML = `${def.headerText} <i class="fas fa-sort"></i>`; // Standardize header text + icon
                 th.addEventListener('click', () => handleColumnSort(def.key)); // Use the data key
            }
        });


        // Clear existing dynamic channel columns (keep static ones)
        const staticHeaderCount = staticColumnDefs.length; // Use definition length
        while (tableHeader.children.length > staticHeaderCount) {
            tableHeader.removeChild(tableHeader.lastChild);
        }
        // Add dynamic channel columns with listeners
        channelColumns.forEach(channel => {
            const th = document.createElement('th');
            th.className = 'sortable';
            th.innerHTML = `${channel} <i class="fas fa-sort"></i>`;
            th.addEventListener('click', () => handleColumnSort(`channels.${channel}`));
            tableHeader.appendChild(th);
        });

        // Update sort icons on headers
        const allHeaders = tableHeader.querySelectorAll('th.sortable');
        allHeaders.forEach(th => {
            const icon = th.querySelector('i');
            let columnKey = '';
            // Find the key associated with this header
            const staticDef = staticColumnDefs.find(def => th.textContent.startsWith(def.headerText));
            if (staticDef) {
                columnKey = staticDef.key;
            } else {
                // Assume dynamic channel column
                const channelName = th.textContent.replace(/ <i.*$/,'').trim(); // Extract channel name
                if (channelColumns.includes(channelName)) {
                     columnKey = `channels.${channelName}`;
                }
            }

            if (icon) {
                if (columnKey === currentSortColumn) {
                    icon.className = currentSortDirection === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down';
                } else {
                    icon.className = 'fas fa-sort';
                }
            }
        });


        // --- Update table body ---
        tableBody.innerHTML = ''; // Clear previous rows
        dataToRender.forEach(item => {
            const row = tableBody.insertRow();
            row.dataset.id = item.id; // Use DB ID

            // Static columns
            row.insertCell().textContent = item.div || '';
            row.insertCell().textContent = item.signature || '';
            row.insertCell().textContent = item.axe || '';
            row.insertCell().textContent = item.subAxe || '';
            row.insertCell().textContent = item.metier || '';
            row.insertCell().textContent = item.ean || '';
            row.insertCell().textContent = item.sku || '';
            row.insertCell().textContent = item.description || '';
            row.insertCell().textContent = (item.units || 0).toLocaleString();
            row.insertCell().textContent = item.plant || ''; // Was item.stockOrigin, now item.plant (which holds description)
            row.insertCell().textContent = item.flagExcess6months || '';
            row.insertCell().textContent = item.flagExcess12months || '';
            const allocAccuCell = row.insertCell();
            // Calculate total allocated for the item initially
            const totalAllocatedInitial = Object.values(item.channels || {}).reduce((sum, val) => sum + (val || 0), 0);
            const remainingQtyInitial = (item.units || 0) - totalAllocatedInitial;
            updateAllocAccuCell(allocAccuCell, item.units || 0, totalAllocatedInitial); // Update Alloc % cell
            const remainingQtyCell = row.insertCell(); // Add Remaining Qty cell
            updateRemainingQtyCell(remainingQtyCell, remainingQtyInitial); // Populate Remaining Qty cell

            // Dynamic channel columns
            channelColumns.forEach(channel => {
                const td = row.insertCell();
                const input = document.createElement('input');
                input.type = 'number';
                input.min = 0;
                input.value = item.channels?.[channel] || 0;
                input.dataset.channel = channel;
                input.dataset.id = item.id; // DB ID
                input.dataset.ean = item.ean; // Store EAN for saving changes
                input.addEventListener('change', handleAllocationChange);
                td.appendChild(input);
            });
        });

        // Update detail metrics after rendering table
        updateDetailMetrics(dataToRender);

        // Validate all inputs after rendering
        validateAllInputs();
    }

    function handleColumnSort(column) {
        if (currentSortColumn === column) {
            currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            currentSortColumn = column;
            currentSortDirection = 'asc';
        }
        renderAllocationTable(); // Re-render table with new sort order
    }

    function handleAllocationChange(event) {
        const input = event.target;
        const rowId = input.closest('tr').dataset.id; // Get the unique row ID (e.g., "ean_plant")
        const channel = input.dataset.channel;
        const value = parseInt(input.value) || 0;

        // Update local data state first
        // Find item by its unique 'id' (ean_plant)
        const item = allocationData.find(d => d.id === rowId); 
        if (item) {
            if (!item.channels) item.channels = {}; // Ensure channels object exists
            item.channels[channel] = value;

            // Recalculate total allocated and remaining quantity for THIS ROW
            const currentInputsInRow = input.closest('tr').querySelectorAll('input[type="number"]');
            const currentTotalAllocatedInRow = Array.from(currentInputsInRow).reduce((sum, inp) => sum + (parseInt(inp.value) || 0), 0);
            const currentRemainingQtyInRow = (item.units || 0) - currentTotalAllocatedInRow;

            // Update local data state for this specific item
            item.allocAccu = calculateAllocAccuString(item.units || 0, currentTotalAllocatedInRow);
            // item.remainingQty = currentRemainingQtyInRow; // Not strictly needed in item state if cell is updated directly

            // Update the specific cells in the DOM for THIS ROW
            const row = input.closest('tr');
            if (row) {
                const accuracyCell = row.cells[12]; // Alloc % cell index
                const remainingQtyCell = row.cells[13]; // Remaining Qty cell index

                if (accuracyCell) {
                    updateAllocAccuCell(accuracyCell, item.units || 0, currentTotalAllocatedInRow);
                }
                if (remainingQtyCell) {
                    updateRemainingQtyCell(remainingQtyCell, currentRemainingQtyInRow);
                }
            }

            // Validate this input and related inputs in the row
            validateInput(input); // This function now also handles the error message visibility

            // Update detail metrics (using currently filtered data)
            updateDetailMetrics(filterData());

            // Update overall status badge after a change
            updateAllocationStatus();
        }
    }

    function validateInput(input) {
        console.log('--- validateInput entered. Input object:', input); // NEW TOP LOG
        if (!input || !input.dataset) {
            console.error('validateInput: Received invalid input object or input.dataset is undefined.');
            return true; // Exit if input is not as expected
        }
        console.log(`validateInput: allocationData length: ${allocationData ? allocationData.length : 'undefined'}. Sample:`, allocationData ? allocationData.slice(0,1) : 'N/A'); // NEW LOG

        const idFromDataset = input.dataset.id; // This is a string
        // Find the item using string comparison, similar to validateAllInputs
        const item = allocationData.find(itemL => String(itemL.id) === idFromDataset);

        if (!item) {
            console.log(`validateInput: Item not found for idFromDataset = ${idFromDataset}. allocationData checked.`); // MODIFIED LOG
            return true; // Cannot validate if item not found
        }

        const row = input.closest('tr');
        if (!row) return true; // Cannot validate if row not found

        const inputs = row.querySelectorAll('input[type="number"]');
        let totalAllocated = 0;

        inputs.forEach(inp => {
            totalAllocated += parseInt(inp.value) || 0;
        });
        console.log(`validateInput for item ID ${item?.id}: item.units = ${item?.units}, calculated totalAllocated from inputs = ${totalAllocated}`); // LOGGING

        const itemUnits = item.units || 0;
        const isOverAllocated = itemUnits > 0 && totalAllocated > itemUnits; // Check only for over-allocation
        console.log(`validateInput for item ID ${item?.id}: isOverAllocated = ${isOverAllocated}`); // LOGGING

        // Update input styling for all inputs in the row based *only* on over-allocation
        inputs.forEach(inp => {
            inp.classList.toggle('error', isOverAllocated);
        });

        // Re-check overall error state *after* updating the current row
        // Show banner ONLY if there are inputs with the 'error' class (i.e., over-allocated rows)
        const anyOverAllocatedRows = document.querySelectorAll('.allocation-table input.error').length > 0;
        if (validationErrors) {
            validationErrors.classList.toggle('hidden', !anyOverAllocatedRows); // Hide if NO over-allocation errors
            console.log(`validateInput for item ID ${item?.id}: validationErrors hidden: ${validationErrors.classList.contains('hidden')}`); // LOGGING
            if (anyOverAllocatedRows && errorMessage) {
                errorMessage.textContent = 'Total allocation exceeds available units for some products.';
            } else if (!anyOverAllocatedRows && errorMessage) {
                 errorMessage.textContent = ''; // Clear message if no errors
            }
        }


        return !isOverAllocated;
    }

    function validateAllInputs() {
        console.log('validateAllInputs: Called'); // LOGGING
        const inputs = document.querySelectorAll('.allocation-table input[type="number"]');
        console.log(`validateAllInputs: Found ${inputs.length} input elements to validate.`); // LOGGING
        const validatedIds = new Set();
        let allValid = true;

        inputs.forEach(input => {
            const idFromDataset = input.dataset.id; // Keep as string
            // Attempt to use validatedIds with the string form of ID.
            // If item.id in allocationData can be numeric, this Set might store mixed types if not careful.
            // For now, let's assume we process based on the string ID from dataset.
            if (!validatedIds.has(idFromDataset)) { // Use string ID for validatedIds check
                validatedIds.add(idFromDataset);
                console.log(`validateAllInputs: Processing idFromDataset = ${idFromDataset}`); // LOGGING
                // Find the item corresponding to this input's row by comparing string versions of IDs
                 const item = allocationData.find(itemL => String(itemL.id) === idFromDataset);
                 if (item) {
                    console.log(`validateAllInputs: Found item for idFromDataset = ${idFromDataset}`, item); // LOGGING
                     // Find one input in the row to trigger validation for the whole row
                     // Ensure querySelector uses the string ID from dataset correctly
                     const rowInput = document.querySelector(`.allocation-table tr[data-id="${idFromDataset}"] input[type="number"]`);
                     if (rowInput) {
                        console.log(`validateAllInputs: Found rowInput for idFromDataset = ${idFromDataset}`, rowInput); // LOGGING
                         const isValid = validateInput(rowInput); // Validate using one input from the row
                         if (!isValid) allValid = false;
                     } else {
                        console.log(`validateAllInputs: Did NOT find rowInput for idFromDataset = ${idFromDataset}`); // LOGGING
                     }
                 } else {
                    console.log(`validateAllInputs: Did NOT find item in allocationData for idFromDataset = ${idFromDataset}`); // LOGGING
                 }
            }
        });
        return allValid;
    }

    function renderAllocationChart(data = filterData()) { // Accept optional data
        if (!allocationChartContainer || !Highcharts) return;

        const uniquePlants = [...new Set(data.map(item => item.plant).filter(Boolean))].sort();
        const plantChannelTotals = {}; // { plant1: { channelA: total, channelB: total }, plant2: { ... } }

        uniquePlants.forEach(plant => {
            plantChannelTotals[plant] = {};
            channelColumns.forEach(channel => {
                plantChannelTotals[plant][channel] = 0;
            });
        });

        data.forEach(item => {
            const plant = item.plant;
            if (!plant || !uniquePlants.includes(plant)) return; // Skip if plant is undefined or not in uniquePlants

            const unitValue = item.units || 0; 
            const cogsValue = item.cogs || 0; 
            const cogsPerUnit = unitValue > 0 ? cogsValue / unitValue : 0; // Ensure this is uncommented and used if needed, or remove if not. For now, keep it.

            // The logic for `value_for_metric` determines what the chart bars represent.
            // Current interpretation: "Total stock (by plant) of EANs that are allocated to a given channel".
            // This means we sum `item.units` (or `item.cogs`) for EAN-Plant items where the EAN is allocated to the channel.
            const value_for_metric = currentMetricView === 'unit' ? item.units : item.cogs;

            channelColumns.forEach(channel => {
                // Check if the EAN of the current item (which is EAN-Plant specific)
                // has any allocation to the current channel.
                // `item.channels` is an object like { channelName: allocatedQtyForEAN, ... }
                if (item.channels?.[channel] && item.channels[channel] > 0) { 
                    plantChannelTotals[plant][channel] += value_for_metric; 
                }
            });
        });

        const series = uniquePlants.map(plant => {
            return {
                name: plant,
                data: channelColumns.map(channel => plantChannelTotals[plant][channel] || 0)
            };
        });

        Highcharts.chart('allocation-chart', {
            chart: { type: 'bar', backgroundColor: 'transparent' },
            colors: ['#4285F4', '#DB4437', '#F4B400', '#0F9D58', '#AB47BC', '#00ACC1', '#FF7043', '#9E9D24', '#5C6BC0', '#26A69A'], // Distinct professional palette
            title: { text: "Stock of EANs Allocated to Channels (by Plant)" },
            xAxis: { categories: channelColumns, crosshair: true, labels: { style: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-color') } } },
            yAxis: {
                min: 0,
                title: { text: currentMetricView === 'unit' ? 'Total Units' : 'Total COGS (€)', style: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-color') } },
                labels: { style: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-color') } },
                stackLabels: {
                    enabled: true,
                    style: {
                        fontWeight: 'bold',
                        color: (Highcharts.defaultOptions.title.style && Highcharts.defaultOptions.title.style.color) || 'gray'
                    }
                }
            },
            tooltip: {
                headerFormat: '<b>{point.x}</b><br/>',
                pointFormat: '{series.name}: {point.y:,.0f}<br/>Total: {point.stackTotal:,.0f}'
            },
            plotOptions: {
                bar: {
                    stacking: 'normal',
                    dataLabels: {
                        enabled: true,
                        formatter: function() {
                            if (this.y > 0) return Highcharts.numberFormat(this.y, 0, '.', ',');
                            return null;
                        },
                        style: { color: '#000000', textOutline: 'none' }
                    }
                }
            },
            series: series,
            credits: { enabled: false }
        });
    }

    function renderDivisionChart(data = filterData()) { // Accept optional data
         if (!divisionChartContainer || !Highcharts) return;

        const divisionData = {};
        data.forEach(item => {
            const div = item.div || 'Unknown';
            if (!divisionData[div]) divisionData[div] = 0;
            const value = currentMetricView === 'unit' ? (item.units || 0) : (item.cogs || 0);
            divisionData[div] += value;
        });

        const chartData = Object.keys(divisionData).map(div => ({ name: div, y: divisionData[div] }));
        const numDivisions = chartData.length > 0 ? chartData.length : 1; // Ensure at least 1 for generateColorShades
        const pieColors = generateColorShades('#ffff3f', '#007f5f', numDivisions);

        Highcharts.chart('division-chart', {
            chart: { type: 'pie', backgroundColor: 'transparent' },
            colors: pieColors,
            title: { text: null },
            tooltip: { pointFormat: '{series.name}: <b>{point.y:,.0f} ' + (currentMetricView === 'unit' ? 'units' : '€') + '</b>' },
            accessibility: { point: { valueSuffix: currentMetricView === 'unit' ? 'units' : '€' } },
            plotOptions: { pie: { allowPointSelect: true, cursor: 'pointer', dataLabels: { enabled: true, format: '<b>{point.name}</b>: {point.percentage:.1f} %', style: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-color') } } } },
            series: [{ name: 'Stock at Risk', data: chartData }],
            credits: { enabled: false }
        });
    }

    function renderBrandChart(data = filterData()) { // Accept optional data
         if (!brandChartContainer || !Highcharts) return;

        const brandData = {};
        data.forEach(item => {
            const brand = item.signature || 'Unknown';
            if (!brandData[brand]) brandData[brand] = 0;
            const value = currentMetricView === 'unit' ? (item.units || 0) : (item.cogs || 0);
            brandData[brand] += value;
        });

        const chartData = Object.keys(brandData)
            .map(brand => ({ name: brand, y: brandData[brand] }))
            .sort((a, b) => b.y - a.y)
            .slice(0, 10); // Show top 10 brands, or fewer if less than 10

        const numBrands = chartData.length > 0 ? chartData.length : 1; // Ensure at least 1 for generateColorShades
        const pieColors = generateColorShades('#ffff3f', '#007f5f', numBrands);


        Highcharts.chart('brand-chart', {
            chart: { type: 'pie', backgroundColor: 'transparent' },
            colors: pieColors,
            title: { text: null },
            tooltip: { pointFormat: '{series.name}: <b>{point.y:,.0f} ' + (currentMetricView === 'unit' ? 'units' : '€') + '</b>' },
            accessibility: { point: { valueSuffix: currentMetricView === 'unit' ? 'units' : '€' } },
            plotOptions: { pie: { allowPointSelect: true, cursor: 'pointer', dataLabels: { enabled: true, format: '<b>{point.name}</b>: {point.percentage:.1f} %', style: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-color') } } } },
            series: [{ name: 'Stock at Risk', data: chartData }],
            credits: { enabled: false }
        });
    }

    function renderAllocationLegend(data = filterData()) { // Accept optional data
        if (!allocationLegend) return;

        const channelTotals = {};
        const channelCogs = {};
        let totalReliability = {};

        channelColumns.forEach(channel => {
            channelTotals[channel] = 0;
            channelCogs[channel] = 0;
            totalReliability[channel] = { total: 0, count: 0 };
        });

        data.forEach(item => {
            const unitValue = item.units || 0;
            const cogsValue = item.cogs || 0; // Total COGS for product inventory from API
            const cogsPerUnit = unitValue > 0 ? cogsValue / unitValue : 0;

            channelColumns.forEach(channel => {
                const allocatedUnits = item.channels?.[channel] || 0;
                channelTotals[channel] += allocatedUnits;
                channelCogs[channel] += allocatedUnits * cogsPerUnit;

                if (allocatedUnits > 0) {
                    const reliability = parseAllocAccu(item.allocAccu || '0%');
                    totalReliability[channel].total += reliability;
                    totalReliability[channel].count++;
                }
            });
        });

        const avgReliability = {};
        channelColumns.forEach(channel => {
            avgReliability[channel] = totalReliability[channel].count > 0
                ? Math.round(totalReliability[channel].total / totalReliability[channel].count)
                : 0;
        });

        // Create legend HTML using channelColumns
        let legendHTML = `
            <div class="legend-row">
                <div class="legend-header">UNITS</div>
                ${channelColumns.map(channel => `<div class="legend-value">${channelTotals[channel].toLocaleString()} Units</div>`).join('')}
            </div>
            <div class="legend-row">
                <div class="legend-header">COGS</div>
                ${channelColumns.map(channel => `<div class="legend-value">${channelCogs[channel].toLocaleString()} €</div>`).join('')}
            </div>
            <div class="legend-row">
                <div class="legend-header">Allocation Reliability</div>
                ${channelColumns.map(channel => `<div class="legend-value">${avgReliability[channel]}%</div>`).join('')}
            </div>
        `;
        allocationLegend.innerHTML = legendHTML;
    }

    // --- Metrics Functions ---
    function updateSummaryMetrics(data = filterData()) { // Accept optional data
        // Calculate totals based on the *filtered* data
        let totalUnits = 0;
        let totalCogs = 0;

        data.forEach(item => {
            totalUnits += (item.units || 0);
            totalCogs += (item.cogs || 0); // Sum the total COGS from fetched data
        });

        // Update UI
        if (totalUnitsEl) totalUnitsEl.textContent = totalUnits.toLocaleString(); // Display full units
        if (totalCogsEl) totalCogsEl.textContent = `${Math.round(totalCogs / 1000)}K€`; // Use K€ for COGS

        // Update legend (already accepts filtered data)
        renderAllocationLegend(data);
    }

    function updateDetailMetrics(data) { // Data here is already filtered and potentially sorted
        // Calculate totals based on the data passed to the function (usually from renderAllocationTable)
        let totalUnits = 0;
        let totalSkus = data.length;

        data.forEach(item => {
            totalUnits += (item.units || 0); // Handle null units
        });

        // Update UI
        if (detailTotalUnitsEl) detailTotalUnitsEl.textContent = totalUnits.toLocaleString();
        if (detailTotalSkusEl) detailTotalSkusEl.textContent = totalSkus;
    }

    // --- Action Functions ---
    async function saveAllocation() {
        if (!validateAllInputs()) {
            alert('Please correct allocation errors before saving.');
            return;
        }

        // Prepare data to send to the backend
        const changesToSave = allocationData.map(item => ({
            ean: item.ean,
            channels: item.channels || {} // Send the updated channel allocations, ensure it's an object
        }));

        console.log("Data to save:", changesToSave);

        const saveBtn = document.getElementById('save-allocation');
        const originalText = saveBtn.innerHTML;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
        saveBtn.disabled = true;

        try {
            const response = await fetch('http://127.0.0.1:5000/api/save_allocations', { // Changed endpoint name
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    // Add auth headers if needed
                },
                body: JSON.stringify(changesToSave)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: 'Failed to save allocations.' }));
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log("Save result:", result);

            saveBtn.innerHTML = '<i class="fas fa-check"></i> Saved!';

            // Re-fetch data to update UI and status
            await fetchAllocationData();

            setTimeout(() => {
                saveBtn.innerHTML = originalText.includes("Save Changes") ? originalText : '<i class="fas fa-save"></i> Save Changes';
                saveBtn.disabled = false;
            }, 1500);

        } catch (error) {
            console.error('Error saving allocation changes:', error);
            alert(`Failed to save changes: ${error.message}`);
            saveBtn.innerHTML = originalText.includes("Save Changes") ? originalText : '<i class="fas fa-save"></i> Save Changes';
            saveBtn.disabled = false;
        }
    }

    async function autoAllocate() {
        console.log("Attempting Auto-Allocation via backend...");
        const autoAllocateBtn = document.getElementById('auto-allocate');
        const originalText = autoAllocateBtn.innerHTML;
        autoAllocateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Allocating...';
        autoAllocateBtn.disabled = true;

        let fetchErrorOccurred = false;
        let fetchErrorMessage = '';
        let directCallSuccessful = false;

        try {
            // Call the backend endpoint to trigger the solver
            const response = await fetch('http://127.0.0.1:5000/api/auto_allocate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    // Add any necessary headers like Authorization if needed
                },
                // Optionally send current filters or other parameters if the backend needs them
                // body: JSON.stringify({ filters: { division: divisionFilterDetail.value, ... } })
            });

            const responseText = await response.text(); 
            console.log("Raw response from /api/auto_allocate:", responseText); 

            if (!response.ok) {
                let errorDetail = `HTTP error! status: ${response.status}`;
                try {
                    const errorJson = JSON.parse(responseText);
                    errorDetail = errorJson.message || errorJson.error || responseText;
                } catch (e) {
                    errorDetail = "Server error (non-JSON response): " + responseText.substring(0, 100) + (responseText.length > 100 ? "..." : "");
                }
                throw new Error(errorDetail); // This error will be caught by the catch block below
            }

            // Try to parse to ensure it's valid JSON
            JSON.parse(responseText); 
            console.log("Successfully received and parsed response from /api/auto_allocate.");
            directCallSuccessful = true; // Mark the direct API call as successful

        } catch (error) {
            // This catch block handles:
            // 1. "Failed to fetch" from the fetch() call itself.
            // 2. Errors thrown if !response.ok.
            // 3. Errors thrown if JSON.parse(responseText) fails.
            fetchErrorOccurred = true;
            fetchErrorMessage = error.message;
            console.error('Error during /api/auto_allocate call or response processing:', fetchErrorMessage);
            if (error.cause) console.error('Cause:', error.cause);
        }

        // Always attempt to refresh data from /api/allocation_data,
        // as the server-side allocation might have completed even if fetching its direct response failed.
        console.log("Now attempting to refresh data with fetchAllocationData() regardless of prior fetch outcome...");
        try {
            await fetchAllocationData(); // Refresh the entire dataset and UI
            console.log("fetchAllocationData() completed after auto-allocate attempt.");
        } catch (refreshError) {
            console.error("Error during subsequent fetchAllocationData():", refreshError.message);
            if (!fetchErrorOccurred) { // If auto_allocate call was fine, but refresh failed
                fetchErrorOccurred = true; // Mark that an error occurred in the overall process
                fetchErrorMessage = `Data refresh failed after allocation: ${refreshError.message}`;
            } else {
                // Append refresh error information if auto_allocate already failed
                fetchErrorMessage += ` | Additionally, data refresh failed: ${refreshError.message}`;
            }
        }
        
        if (fetchErrorOccurred) {
            alert(`Auto-allocation process encountered an issue: ${fetchErrorMessage}`);
        } else if (directCallSuccessful) {
            // Only show "Allocated!" if the direct /api/auto_allocate call was successful AND no subsequent refresh error
            autoAllocateBtn.innerHTML = '<i class="fas fa-check"></i> Allocated!';
        }

        // Restore button text and enable it after a delay.
        // The button text will show "Allocated!" only if directCallSuccessful and no fetchErrorOccurred.
        // Otherwise, it reverts to original text.
        setTimeout(() => {
             if (directCallSuccessful && !fetchErrorOccurred) {
                 // Keep "Allocated!" for a bit then revert
                 autoAllocateBtn.innerHTML = originalText.includes("Auto-Allocate") ? originalText : '<i class="fas fa-magic"></i> Auto-Allocate';
             } else {
                 // If there was any error, or direct call wasn't marked successful, revert directly
                 autoAllocateBtn.innerHTML = originalText.includes("Auto-Allocate") ? originalText : '<i class="fas fa-magic"></i> Auto-Allocate';
             }
             autoAllocateBtn.disabled = false;
        }, (directCallSuccessful && !fetchErrorOccurred) ? 1500 : 500); // Shorter delay if error or reverting without success message
    }

    async function validateAllocation() {
        if (document.querySelectorAll('.allocation-table input.error').length > 0) {
            alert('Please correct allocation errors before validating.');
            return;
        }

        // TODO: Implement API call to validate and update status
        console.log("Validating allocation...");
        alert("Validation functionality not yet implemented.");

        // Simulate validation process
        const validateBtn = document.getElementById('validate-allocation-btn');
        const originalText = validateBtn.innerHTML;
        validateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Validating...';
        validateBtn.disabled = true;

        // Replace setTimeout with actual fetch call
        // fetch('/api/validate_allocation', { method: 'POST' }) // Send run ID if needed
        // .then(response => response.json())
        // .then(data => { if(data.status === 'VALIDATED') { ... update UI ... } else { ... handle error ... } })
        // .catch(error => { ... handle error ... })
        // .finally(() => { ... restore button ... });

        setTimeout(() => { // Keep simulation for now
            validateBtn.innerHTML = '<i class="fas fa-check"></i> Validated!';
            // Simulate API update and re-fetch which will update the status
            // For simulation, directly update:
            currentAllocationStatus = 'VALIDATED';
            updateAllocationStatus(); // Update the badge display
            // fetchAllocationData(); // In a real scenario, re-fetch after API call

            setTimeout(() => {
                validateBtn.innerHTML = originalText.includes("VALIDATE") ? originalText : '<i class="fas fa-check-circle"></i> VALIDATE FINAL ALLOCATION';
                validateBtn.disabled = false;
            }, 1500);
        }, 1000);
    }

    function runAllocation() {
        // This function likely corresponds to the old form/API structure.
        // Decide if it's still needed or should trigger the new solver via a different mechanism.
        // For now, keep the simulation but note it might need removal/rework.
        alert("Run Allocation (from original form) functionality needs review/update for new UI/API.");
        if(statusMessage) {
            statusMessage.textContent = 'Running allocation...';
            statusMessage.style.color = 'orange';
        }

        // TODO: Update this to call the appropriate backend endpoint if this button is kept.
        // This might involve collecting data from the old form elements if they still exist.

        setTimeout(() => {
             if(statusMessage) {
                statusMessage.textContent = 'Allocation successful! (Simulated)';
                statusMessage.style.color = 'green';
            }
            // Refresh data using the new fetch function
            fetchAllocationData();
        }, 1500);
    }

    // --- Export Functions ---
    function exportToExcel(filename) {
        const data = filterData(); // Get currently filtered data

        const wsData = [];
        // Header row
        const headerRow = ['Div', 'Signature', 'Axe', 'SubAxe', 'Metier', 'EAN', 'SKU', 'Description', 'Units', 'Plant', 'FlagExcess6months', 'FlagExcess12months', 'Allocation %', 'Remaining Qty']; // Changed 'Stock origin' to 'Plant'
        channelColumns.forEach(channel => headerRow.push(channel)); // Use dynamic channel columns
        wsData.push(headerRow);

        // Data rows
        data.forEach(item => {
            const totalAllocated = Object.values(item.channels || {}).reduce((sum, val) => sum + (val || 0), 0);
            const remainingQty = (item.units || 0) - totalAllocated;
            const allocPerc = calculateAllocAccuString(item.units || 0, totalAllocated); // Recalculate for export

            const row = [
                item.div || '',
                item.signature || '',
                item.axe || '',
                item.subAxe || '',
                item.metier || '',
                item.ean || '',
                item.sku || '',
                item.description || '',
                item.units || 0,
                item.plant || '', // Was item.stockOrigin, now item.plant (which holds description)
                item.flagExcess6months || '',
                item.flagExcess12months || '',
                allocPerc, // Use calculated percentage string
                remainingQty // Add remaining quantity
            ];
            channelColumns.forEach(channel => {
                row.push(item.channels?.[channel] || 0);
            });
            wsData.push(row);
        });

        if (typeof XLSX === 'undefined' || typeof saveAs === 'undefined') {
             console.error("XLSX or FileSaver library not loaded.");
             alert("Export functionality requires external libraries (XLSX, FileSaver). Check console.");
             return;
        }

        const wb = XLSX.utils.book_new();
        const ws = XLSX.utils.aoa_to_sheet(wsData);
        XLSX.utils.book_append_sheet(wb, ws, 'Allocation Data');
        const excelBuffer = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
        saveAsExcelFile(excelBuffer, filename);
    }

    function saveAsExcelFile(buffer, fileName) {
        const data = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
        const date = new Date().toISOString().slice(0, 10);
        // Use FileSaver.js saveAs function
        saveAs(data, `${fileName}_${date}.xlsx`);
    }

    // --- Status Update Function ---
    function updateAllocationStatus() {
        if (!allocationStatusEl) return;

        // Prioritize API status if it's definitive (Validated, Error, Failed)
        // Note: Assuming API returns status like 'VALIDATED', 'IN_PROGRESS', 'ERROR', 'FAILED' or similar
        // We need to know the exact possible values from the API. Let's assume 'VALIDATED', 'ERROR', 'FAILED'.
        const apiStatus = allocationData.length > 0 ? (allocationData[0]?.api_status || 'UNKNOWN') : 'UNKNOWN'; // Example: Get status from data if available

        if (apiStatus === 'VALIDATED') {
            currentAllocationStatus = 'Allocation Validated';
            allocationStatusEl.textContent = currentAllocationStatus;
            allocationStatusEl.style.backgroundColor = 'var(--success-color)';
            return;
        } else if (apiStatus === 'ERROR' || apiStatus === 'FAILED') {
             currentAllocationStatus = apiStatus; // Show API error status
             allocationStatusEl.textContent = currentAllocationStatus;
             allocationStatusEl.style.backgroundColor = 'var(--error-color)';
             return;
        }

        // If API status is not definitive, determine based on current data
        let totalUnitsToAllocate = 0;
        let totalAllocatedUnits = 0;
        let hasPartialAllocation = false;

        allocationData.forEach(item => {
            const itemUnits = item.units || 0;
            totalUnitsToAllocate += itemUnits;
            const itemAllocated = Object.values(item.channels || {}).reduce((sum, val) => sum + (val || 0), 0);
            totalAllocatedUnits += itemAllocated;
            if (itemAllocated > 0 && itemAllocated < itemUnits) {
                hasPartialAllocation = true;
            }
        });

        if (totalAllocatedUnits === 0 && totalUnitsToAllocate > 0) {
            currentAllocationStatus = 'Allocation to be done';
            allocationStatusEl.style.backgroundColor = 'var(--status-badge)'; // Yellow
        } else if (totalAllocatedUnits > 0 || hasPartialAllocation) {
             currentAllocationStatus = 'Allocation in progress';
             allocationStatusEl.style.backgroundColor = 'var(--status-badge)'; // Yellow
        } else if (totalUnitsToAllocate === 0) {
             currentAllocationStatus = 'No Data'; // Or 'Ready' if applicable
             allocationStatusEl.style.backgroundColor = 'var(--text-light)'; // Grayish
        } else {
             // Default case if something unexpected happens
             currentAllocationStatus = 'IN PROGRESS'; // Fallback
             allocationStatusEl.style.backgroundColor = 'var(--status-badge)';
        }

        allocationStatusEl.textContent = currentAllocationStatus;
    }


    // --- Utility Functions ---
    function parseAllocAccu(allocAccu) {
        // Handle potential null or undefined input
        return parseInt((allocAccu || '0%').replace('%', ''), 10); // Keep this for parsing the string if needed elsewhere
    }

    // Helper to calculate the allocation percentage string
    function calculateAllocAccuString(itemUnits, totalAllocated) {
        let percentage = 0;
        if (itemUnits > 0) {
            // Use Math.round and allow over 100%
            percentage = Math.round((totalAllocated / itemUnits) * 100);
        } else if (totalAllocated > 0) {
            percentage = Infinity; // Indicate allocation with zero available units
        }
        return `${percentage}%`;
    }

    // Helper function to update the Allocation % cell content
    function updateAllocAccuCell(cell, itemUnits, totalAllocated) {
        const percentageString = calculateAllocAccuString(itemUnits, totalAllocated);
        cell.textContent = percentageString;
        // Optional: Add styling based on percentage if needed (e.g., red if > 100)
        cell.classList.toggle('over-allocated-perc', itemUnits > 0 && totalAllocated > itemUnits);
    }

    // Helper function to update the Remaining Qty cell content and style
    function updateRemainingQtyCell(cell, remainingQty) {
        cell.textContent = remainingQty.toLocaleString();
        cell.classList.remove('negative-qty', 'positive-qty', 'zero-qty'); // Clear previous classes
        if (remainingQty < 0) {
            cell.classList.add('negative-qty');
        } else if (remainingQty > 0) {
            cell.classList.add('positive-qty');
        } else {
            cell.classList.add('zero-qty');
        }
    }

    // --- Utility Functions ---
    function parseAllocAccu(allocAccu) {
        // Handle potential null or undefined input
        return parseInt((allocAccu || '0%').replace('%', ''), 10); // Keep this for parsing the string if needed elsewhere
    }

    // Helper to calculate the allocation percentage string
    function calculateAllocAccuString(itemUnits, totalAllocated) {
        let percentage = 0;
        if (itemUnits > 0) {
            // Use Math.round and allow over 100%
            percentage = Math.round((totalAllocated / itemUnits) * 100);
        } else if (totalAllocated > 0) {
            percentage = Infinity; // Indicate allocation with zero available units
        }
        return `${percentage}%`;
    }

    // Helper function to update the Allocation % cell content
    function updateAllocAccuCell(cell, itemUnits, totalAllocated) {
        const percentageString = calculateAllocAccuString(itemUnits, totalAllocated);
        cell.textContent = percentageString;
        // Optional: Add styling based on percentage if needed (e.g., red if > 100)
        cell.classList.toggle('over-allocated-perc', itemUnits > 0 && totalAllocated > itemUnits);
    }

    // Helper function to update the Remaining Qty cell content and style
    function updateRemainingQtyCell(cell, remainingQty) {
        cell.textContent = remainingQty.toLocaleString();
        cell.classList.remove('negative-qty', 'positive-qty', 'zero-qty'); // Clear previous classes
        if (remainingQty < 0) {
            cell.classList.add('negative-qty');
        } else if (remainingQty > 0) {
            cell.classList.add('positive-qty');
        } else {
            cell.classList.add('zero-qty');
        }
    }

    function parseHexColor(hex) {
        let r = 0, g = 0, b = 0;
        if (hex.length === 4) { // #RGB
            r = parseInt(hex[1] + hex[1], 16);
            g = parseInt(hex[2] + hex[2], 16);
            b = parseInt(hex[3] + hex[3], 16);
        } else if (hex.length === 7) { // #RRGGBB
            r = parseInt(hex[1] + hex[2], 16);
            g = parseInt(hex[3] + hex[4], 16);
            b = parseInt(hex[5] + hex[6], 16);
        }
        return [r, g, b];
    }

    function rgbToHex(r, g, b) {
        return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1).toUpperCase();
    }

    function generateColorShades(startColorHex, endColorHex, numShades) {
        if (numShades <= 0) return [];
        if (numShades === 1) return [startColorHex];

        const shades = [];
        const [r1, g1, b1] = parseHexColor(startColorHex);
        const [r2, g2, b2] = parseHexColor(endColorHex);

        for (let i = 0; i < numShades; i++) {
            const t = numShades === 1 ? 0.5 : i / (numShades - 1); // Avoid division by zero if numShades is 1
            const r = Math.round(r1 + t * (r2 - r1));
            const g = Math.round(g1 + t * (g2 - g1));
            const b = Math.round(b1 + t * (b2 - b1));
            shades.push(rgbToHex(r, g, b));
        }
        return shades;
    }

    // --- Initialize Application ---
    initializeApp();
});
