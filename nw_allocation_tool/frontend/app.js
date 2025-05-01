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
        [divisionFilterSummary, brandFilterSummary, categoryFilterSummary].forEach(filter => {
            filter.addEventListener('change', () => {
                const filtered = filterData(); // Apply filters first
                renderAllocationChart(filtered); // Pass filtered data to render functions
                renderDivisionChart(filtered);
                renderBrandChart(filtered);
                updateSummaryMetrics(filtered);
                renderAllocationLegend(filtered);
            });
        });

        [divisionFilterDetail, brandFilterDetail, categoryFilterDetail].forEach(filter => {
            filter.addEventListener('change', () => {
                renderAllocationTable(); // Re-render table with new filters applied
            });
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
            renderAllocationTable(); // Render table with initial data
            if (validationErrors) validationErrors.classList.add('hidden'); // Ensure banner is hidden initially

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

        // Populate division filters
        populateFilterOptions(divisionFilterSummary, divisions);
        populateFilterOptions(divisionFilterDetail, divisions);

        // Populate brand filters
        populateFilterOptions(brandFilterSummary, brands);
        populateFilterOptions(brandFilterDetail, brands);

        // Populate category filters
        populateFilterOptions(categoryFilterSummary, categories);
        populateFilterOptions(categoryFilterDetail, categories);
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
        const divisionFilter = (isDetailView ? divisionFilterDetail.value : divisionFilterSummary.value) || 'all';
        const brandFilter = (isDetailView ? brandFilterDetail.value : brandFilterSummary.value) || 'all';
        const categoryFilter = (isDetailView ? categoryFilterDetail.value : categoryFilterSummary.value) || 'all';

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
            { headerText: 'EAN', key: 'ean' },
            { headerText: 'Hierarchy', key: 'hierarchy' },
            { headerText: 'Name', key: 'name' },
            { headerText: 'Units', key: 'units' },
            { headerText: 'Stock origin', key: 'stockOrigin' },
            { headerText: 'Allocation %', key: 'allocAccu' },
            { headerText: 'Remaining Qty', key: 'remainingQty' } // Added column definition
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
            row.insertCell().textContent = item.ean || '';
            row.insertCell().textContent = item.hierarchy || '';
            // Photo cell removed
            row.insertCell().textContent = item.name || '';
            row.insertCell().textContent = (item.units || 0).toLocaleString();
            row.insertCell().textContent = item.stockOrigin || '';
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
        const id = parseInt(input.dataset.id); // DB ID
        const channel = input.dataset.channel;
        const value = parseInt(input.value) || 0;

        // Update local data state first
        const item = allocationData.find(item => item.id === id);
        if (item) {
            if (!item.channels) item.channels = {}; // Ensure channels object exists
            item.channels[channel] = value;

            // Recalculate total allocated and remaining quantity
            const currentInputs = input.closest('tr').querySelectorAll('input[type="number"]');
            const currentTotalAllocated = Array.from(currentInputs).reduce((sum, inp) => sum + (parseInt(inp.value) || 0), 0);
            const currentRemainingQty = (item.units || 0) - currentTotalAllocated;

            // Update local data state
            item.allocAccu = calculateAllocAccuString(item.units || 0, currentTotalAllocated);
            item.remainingQty = currentRemainingQty; // Store remaining qty in local state if needed

            // Update the specific cells in the DOM
            const row = input.closest('tr');
            if (row) {
                const accuracyCell = row.cells[7]; // Alloc % cell (index 7)
                const remainingQtyCell = row.cells[8]; // Remaining Qty cell (index 8)

                if (accuracyCell) {
                    updateAllocAccuCell(accuracyCell, item.units || 0, currentTotalAllocated);
                }
                if (remainingQtyCell) {
                    updateRemainingQtyCell(remainingQtyCell, currentRemainingQty);
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
        const id = parseInt(input.dataset.id); // DB ID
        const item = allocationData.find(item => item.id === id);

        if (!item) return true; // Cannot validate if item not found

        const row = input.closest('tr');
        if (!row) return true; // Cannot validate if row not found

        const inputs = row.querySelectorAll('input[type="number"]');
        let totalAllocated = 0;

        inputs.forEach(inp => {
            totalAllocated += parseInt(inp.value) || 0;
        });

        const itemUnits = item.units || 0;
        const isOverAllocated = itemUnits > 0 && totalAllocated > itemUnits; // Check only for over-allocation

        // Update input styling for all inputs in the row based *only* on over-allocation
        inputs.forEach(inp => {
            inp.classList.toggle('error', isOverAllocated);
        });

        // Re-check overall error state *after* updating the current row
        // Show banner ONLY if there are inputs with the 'error' class (i.e., over-allocated rows)
        const anyOverAllocatedRows = document.querySelectorAll('.allocation-table input.error').length > 0;
        if (validationErrors) {
            validationErrors.classList.toggle('hidden', !anyOverAllocatedRows); // Hide if NO over-allocation errors
            if (anyOverAllocatedRows && errorMessage) {
                errorMessage.textContent = 'Total allocation exceeds available units for some products.';
            } else if (!anyOverAllocatedRows && errorMessage) {
                 errorMessage.textContent = ''; // Clear message if no errors
            }
        }


        return !isOverAllocated;
    }

    function validateAllInputs() {
        const inputs = document.querySelectorAll('.allocation-table input[type="number"]');
        const validatedIds = new Set();
        let allValid = true;

        inputs.forEach(input => {
            const id = parseInt(input.dataset.id);
            if (!validatedIds.has(id)) {
                validatedIds.add(id);
                // Find the item corresponding to this input's row
                 const item = allocationData.find(item => item.id === id);
                 if (item) {
                     // Find one input in the row to trigger validation for the whole row
                     const rowInput = document.querySelector(`.allocation-table tr[data-id="${id}"] input[type="number"]`);
                     if (rowInput) {
                         const isValid = validateInput(rowInput); // Validate using one input from the row
                         if (!isValid) allValid = false;
                     }
                 }
            }
        });
        return allValid;
    }

    function renderAllocationChart(data = filterData()) { // Accept optional data
        if (!allocationChartContainer || !Highcharts) return;

        // Calculate totals for each channel based on the current metric view
        const channelTotals = {};
        let grandTotal = 0;

        channelColumns.forEach(channel => { channelTotals[channel] = 0; });

        data.forEach(item => {
            const unitValue = item.units || 0;
            const cogsValue = item.cogs || 0; // Total COGS for product inventory from API
            const cogsPerUnit = unitValue > 0 ? cogsValue / unitValue : 0;

            channelColumns.forEach(channel => {
                const allocatedUnits = item.channels?.[channel] || 0;
                const value = currentMetricView === 'unit'
                    ? allocatedUnits
                    : allocatedUnits * cogsPerUnit;
                channelTotals[channel] += value;
            });
        });
        grandTotal = Object.values(channelTotals).reduce((sum, val) => sum + val, 0);

        const chartData = channelColumns.map(channel => {
            const percentage = grandTotal > 0 ? (channelTotals[channel] / grandTotal) * 100 : 0;
            return {
                name: channel,
                y: parseFloat(percentage.toFixed(1)),
                value: channelTotals[channel]
            };
        });

        const colors = { /* ... colors ... */
             'Outlet': '#7CB5EC', 'F&F': '#F7DC6F', 'Liquidation': '#D3D3D3',
             'Donation': '#F8C471', 'Giverny': '#5DADE2', 'Village': '#F4D03F', 'Corbeil': '#A569BD'
        };

        Highcharts.chart('allocation-chart', {
            chart: { type: 'column', backgroundColor: 'transparent' },
            title: { text: null },
            xAxis: { categories: channelColumns, crosshair: true, labels: { style: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-color') } } },
            yAxis: { min: 0, max: 100, title: { text: '%', style: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-color') } }, labels: { style: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-color') } } },
            tooltip: { headerFormat: '<span style="font-size:10px">{point.key}</span><table>', pointFormat: '<tr><td style="padding:0"><b>{point.y:.1f}%</b></td></tr><tr><td style="padding:0">{point.value:,.0f} ' + (currentMetricView === 'unit' ? 'units' : '€') + '</td></tr>', footerFormat: '</table>', shared: true, useHTML: true },
            plotOptions: { column: { pointPadding: 0.2, borderWidth: 0 } },
            series: [{ name: 'Allocation', showInLegend: false, data: chartData.map(point => ({ y: point.y, value: point.value, color: colors[point.name] || '#7CB5EC' })) }],
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

        Highcharts.chart('division-chart', {
            chart: { type: 'pie', backgroundColor: 'transparent' },
            title: { text: null },
            tooltip: { pointFormat: '{series.name}: <b>{point.y:,.0f} ' + (currentMetricView === 'unit' ? 'units' : '€') + '</b>' },
            accessibility: { point: { valueSuffix: currentMetricView === 'unit' ? 'units' : '€' } },
            plotOptions: { pie: { allowPointSelect: true, cursor: 'pointer', dataLabels: { enabled: true, format: '<b>{point.name}</b>: {point.percentage:.1f} %', style: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-color') } } } },
            series: [{ name: 'Stock at Risk', colorByPoint: true, data: chartData }], // Updated series name
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
            .slice(0, 5); // Top 5

        Highcharts.chart('brand-chart', {
            chart: { type: 'pie', backgroundColor: 'transparent' },
            title: { text: null },
            tooltip: { pointFormat: '{series.name}: <b>{point.y:,.0f} ' + (currentMetricView === 'unit' ? 'units' : '€') + '</b>' },
            accessibility: { point: { valueSuffix: currentMetricView === 'unit' ? 'units' : '€' } },
            plotOptions: { pie: { allowPointSelect: true, cursor: 'pointer', dataLabels: { enabled: true, format: '<b>{point.name}</b>: {point.percentage:.1f} %', style: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-color') } } } },
            series: [{ name: 'Stock at Risk', colorByPoint: true, data: chartData }], // Updated series name
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

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: 'Failed to run auto-allocation.' }));
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log("Auto-allocation result:", result);

            // Assuming success means the backend updated the data,
            // so we re-fetch the latest allocation data to refresh the UI
            await fetchAllocationData(); // Refresh the entire dataset and UI

            // Update button text briefly to show success
            autoAllocateBtn.innerHTML = '<i class="fas fa-check"></i> Allocated!';
            setTimeout(() => {
                 autoAllocateBtn.innerHTML = originalText.includes("Auto-Allocate") ? originalText : '<i class="fas fa-magic"></i> Auto-Allocate';
                 autoAllocateBtn.disabled = false;
            }, 1500);


        } catch (error) {
            console.error('Error during auto-allocation:', error);
            alert(`Auto-allocation failed: ${error.message}`);
            // Restore button immediately on error
            autoAllocateBtn.innerHTML = originalText.includes("Auto-Allocate") ? originalText : '<i class="fas fa-magic"></i> Auto-Allocate';
            autoAllocateBtn.disabled = false;
        }
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
        const headerRow = ['Division', 'Brand', 'EAN', 'Category', 'Product Name', 'Total Units', 'Stock Origin', 'Allocation %', 'Remaining Qty']; // Updated header
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
                item.ean || '',
                item.hierarchy || '',
                item.name || '',
                item.units || 0,
                item.stockOrigin || '',
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

    // --- Initialize Application ---
    initializeApp();
});
