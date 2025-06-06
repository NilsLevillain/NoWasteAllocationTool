document.addEventListener('DOMContentLoaded', function() {
    const eanTitle = document.getElementById('eanTitle');
    const pageTitle = document.getElementById('pageTitle');
    const productInfoDiv = document.getElementById('productInfo');
    const totalBadStockEl = document.getElementById('totalBadStock');
    const badStockBreakdownDiv = document.getElementById('badStockBreakdown');
    const totalExistingChannelStockEl = document.getElementById('totalExistingChannelStock');
    const existingChannelStockBreakdownDiv = document.getElementById('existingChannelStockBreakdown');
    const channelPerformanceDiv = document.getElementById('channelPerformance');
    const appliedRulesDiv = document.getElementById('appliedRules');
    const solverConstraintsSummaryDiv = document.getElementById('solverConstraintsSummary');
    const finalAllocationDiv = document.getElementById('finalAllocation');
    const loadingIndicator = document.getElementById('loading-indicator');
    const errorMessageDiv = document.getElementById('error-message');
    const eanDetailsContainer = document.getElementById('eanDetailsContainer');
    const backButton = document.getElementById('backButton');

    const urlParams = new URLSearchParams(window.location.search);
    const ean = urlParams.get('ean');

    if (ean) {
        eanTitle.textContent = ean;
        pageTitle.textContent = `EAN Deep Dive: ${ean}`;
        fetchEanData(ean);
    } else {
        showError("EAN parameter is missing in the URL.");
    }

    backButton.addEventListener('click', () => {
        window.history.back(); // Or redirect to a specific page like index.html
    });

    async function fetchEanData(eanValue) {
        loadingIndicator.style.display = 'block';
        errorMessageDiv.style.display = 'none';
        eanDetailsContainer.style.display = 'none';

        try {
            const response = await fetch(`/api/ean_deep_dive_data?ean=${eanValue}`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: `HTTP error! status: ${response.status}` }));
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            populatePage(data);
            eanDetailsContainer.style.display = 'block';
        } catch (error) {
            console.error('Error fetching EAN data:', error);
            showError(`Failed to load EAN data: ${error.message}`);
        } finally {
            loadingIndicator.style.display = 'none';
        }
    }

    function showError(message) {
        errorMessageDiv.textContent = message;
        errorMessageDiv.style.display = 'block';
        loadingIndicator.style.display = 'none';
        eanDetailsContainer.style.display = 'none';
    }

    function populatePage(data) {
        // Section 0: Product Information
        if (data.product_info && !data.product_info.error) {
            productInfoDiv.innerHTML = `
                <div class="info-item"><strong>Description:</strong> ${data.product_info.description || 'N/A'}</div>
                <div class="info-item"><strong>Brand:</strong> ${data.product_info.brand || 'N/A'}</div>
                <div class="info-item"><strong>Division:</strong> ${data.product_info.division || 'N/A'}</div>
                <div class="info-item"><strong>Axe:</strong> ${data.product_info.axe || 'N/A'}</div>
                <div class="info-item"><strong>Sub-Axe:</strong> ${data.product_info.sub_axe || 'N/A'}</div>
                <div class="info-item"><strong>Metier:</strong> ${data.product_info.metier || 'N/A'}</div>
                <div class="info-item"><strong>SKU:</strong> ${data.product_info.sku || 'N/A'}</div>
            `;
        } else {
            productInfoDiv.innerHTML = `<p class="text-danger">${data.product_info.error || 'Product information not available.'}</p>`;
        }

        // Section 1: Initial Stock & Inventory Status
        totalBadStockEl.textContent = data.initial_stock?.bad_stock_to_allocate || 0;
        if (data.initial_stock?.bad_stock_plant_breakdown?.length > 0) {
            let breakdownHtml = '<table class="table table-sm table-bordered"><thead><tr><th>Plant Code</th><th>Plant Name</th><th>Quantity</th><th>6m+ Excess</th><th>12m+ Excess</th></tr></thead><tbody>';
            data.initial_stock.bad_stock_plant_breakdown.forEach(p => {
                breakdownHtml += `<tr><td>${p.plant_code}</td><td>${p.plant_description}</td><td>${p.quantity}</td><td>${p.flag_excess_6m}</td><td>${p.flag_excess_12m}</td></tr>`;
            });
            breakdownHtml += '</tbody></table>';
            badStockBreakdownDiv.innerHTML = breakdownHtml;
        } else {
            badStockBreakdownDiv.innerHTML = '<p>No plant breakdown available for bad stock.</p>';
        }

        totalExistingChannelStockEl.textContent = data.initial_stock?.total_existing_channel_stock || 0;
        if (data.initial_stock?.existing_channel_stock_breakdown?.length > 0) {
            let existingStockHtml = '<table class="table table-sm table-bordered"><thead><tr><th>Channel ID</th><th>Channel Name</th><th>Quantity</th></tr></thead><tbody>';
            data.initial_stock.existing_channel_stock_breakdown.forEach(s => {
                existingStockHtml += `<tr><td>${s.channel_id}</td><td>${s.channel_name}</td><td>${s.quantity}</td></tr>`;
            });
            existingStockHtml += '</tbody></table>';
            existingChannelStockBreakdownDiv.innerHTML = existingStockHtml;
        } else {
            existingChannelStockBreakdownDiv.innerHTML = '<p>No existing stock in channels for this EAN.</p>';
        }
        
        // Section 2: Demand & Sales Performance
        if (data.channel_performance?.length > 0) {
            let perfHtml = '';
            data.channel_performance.forEach(ch => {
                perfHtml += `
                    <div class="channel-card">
                        <h4>${ch.channel_name} (${ch.channel_id})</h4>
                        <p><strong>Type:</strong> ${ch.channel_type}</p>
                        <p><strong>Sell-Out Qty:</strong> ${ch.sellout_qty}</p>
                        <p><strong>Calculated Demand:</strong> ${ch.calculated_demand}</p>
                        <p><strong>ABC Class:</strong> ${ch.abc_class}</p>
                    </div>`;
            });
            channelPerformanceDiv.innerHTML = perfHtml;
        } else {
            channelPerformanceDiv.innerHTML = '<p>No channel performance data available for this EAN.</p>';
        }

        // Section 3: Applicable Rules
        if (data.applied_rules?.length > 0) {
            let rulesHtml = '';
            data.applied_rules.forEach(ch_rule => {
                rulesHtml += `
                    <div class="channel-card">
                        <h4>${data.channel_performance.find(cp => cp.channel_id === ch_rule.channel_id)?.channel_name || ch_rule.channel_id} (${ch_rule.channel_id})</h4>
                        <p><strong>Coverage Rule:</strong> ${ch_rule.coverage_rule}</p>
                        <p><strong>Push New SKU Rule:</strong> ${ch_rule.push_new_sku_rule}</p>
                        <p><strong>Outlet SKU Capacity Rule:</strong> ${ch_rule.outlet_sku_capacity_rule}</p>
                        <p><strong>Outlet Assortment Rule:</strong> ${ch_rule.outlet_assortment_rule}</p>
                        <p><strong>Restricted Brand (Donation):</strong> ${ch_rule.restricted_brand_donation_rule}</p>
                    </div>`;
            });
            appliedRulesDiv.innerHTML = rulesHtml;
        } else {
            appliedRulesDiv.innerHTML = '<p>No specific rule applications to display for this EAN.</p>';
        }

        // Section 4: Solver Constraints Summary (Placeholder)
        // solverConstraintsSummaryDiv.innerHTML = data.solver_constraints_summary.join('<br>') || '<p>No solver constraint summary available.</p>';
        // For now, the placeholder text in HTML is fine.

        // Section 5: Final Allocation
        if (data.final_allocation?.length > 0) {
            let finalAllocHtml = '<table class="table table-sm table-bordered"><thead><tr><th>Channel ID</th><th>Quantity Allocated</th><th>Allocation Date</th></tr></thead><tbody>';
            data.final_allocation.forEach(fa => {
                finalAllocHtml += `<tr><td>${fa.channel_id}</td><td>${fa.quantity_allocated}</td><td>${fa.allocation_date ? new Date(fa.allocation_date).toLocaleString() : 'N/A'}</td></tr>`;
            });
            finalAllocHtml += '</tbody></table>';
            finalAllocationDiv.innerHTML = finalAllocHtml;
        } else {
            finalAllocationDiv.innerHTML = '<p>No final allocations found in the database for this EAN.</p>';
        }
    }
});
