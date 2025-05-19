/**
 * CQI-9 Compliance Analysis System - Main JavaScript
 * Common functionality for the web portal
 */

// Enable tooltips and popovers from Bootstrap
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize Bootstrap popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Add active class to current nav item
    const currentPath = window.location.pathname;
    document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
        const href = link.getAttribute('href');
        if (href && (currentPath === href || currentPath.startsWith(href + '/'))) {
            link.classList.add('active');
        }
    });

    // Attach event listeners to all analyze buttons
    document.querySelectorAll('.analyze-btn').forEach(button => {
        button.addEventListener('click', function() {
            const requirementId = this.getAttribute('data-requirement-id');
            analyzeEvidence(requirementId);
        });
    });

    // Attach event listeners to all section analyze buttons
    document.querySelectorAll('.analyze-section-btn').forEach(button => {
        button.addEventListener('click', function() {
            const sectionId = this.getAttribute('data-section');
            analyzeSection(sectionId);
        });
    });
});

/**
 * Format a date string to a more readable format
 * @param {string} dateString - Date string to format
 * @returns {string} Formatted date string
 */
function formatDate(dateString) {
    if (!dateString) return '';
    
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return date.toLocaleDateString(undefined, options);
}

/**
 * Format a number with specified decimal places
 * @param {number} value - Number to format
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted number string
 */
function formatNumber(value, decimals = 2) {
    if (value === null || value === undefined || isNaN(value)) return '';
    return Number(value).toFixed(decimals);
}

/**
 * Display a notification message
 * @param {string} message - Message to display
 * @param {string} type - Message type (success, warning, danger, info)
 * @param {number} duration - Duration in milliseconds
 */
function showNotification(message, type = 'info', duration = 5000) {
    const container = document.getElementById('notification-container') || createNotificationContainer();
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    container.appendChild(alert);
    
    // Remove after duration
    if (duration > 0) {
        setTimeout(() => {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 250);
        }, duration);
    }
}

/**
 * Create a notification container if it doesn't exist
 * @returns {HTMLElement} The notification container
 */
function createNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'notification-container';
    container.style.position = 'fixed';
    container.style.top = '20px';
    container.style.right = '20px';
    container.style.zIndex = '1050';
    container.style.width = '300px';
    
    document.body.appendChild(container);
    return container;
}

/**
 * Confirm an action with a modal dialog
 * @param {string} message - Confirmation message
 * @param {Function} callback - Callback function to execute if confirmed
 */
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Function to analyze a single requirement
function analyzeEvidence(requirementId) {
    const evidenceTextarea = document.querySelector(`textarea[data-requirement-id="${requirementId}"]`);
    const evidence = evidenceTextarea ? evidenceTextarea.value.trim() : '';
    
    if (!evidence) {
        alert('Please provide objective evidence before analyzing.');
        return;
    }
    
    // Find the requirement text - improved DOM navigation
    let requirementText = '';
    const row = evidenceTextarea.closest('tr');
    
    // Log for debugging
    console.log("Looking for requirement text for:", requirementId);
    
    // First try to find it in the previous row that has the requirement text
    if (row && row.previousElementSibling) {
        const requirementCell = row.previousElementSibling.querySelector('td:nth-child(2)');
        if (requirementCell) {
            requirementText = requirementCell.textContent.trim();
            console.log("Found requirement in previous row:", requirementText);
        }
    }
    
    // If not found, look for the requirement by its heading
    if (!requirementText) {
        // Find the heading row that contains the requirement ID number (e.g., 1.1, 1.2)
        const reqIdParts = requirementId.split('.');
        const sectionId = reqIdParts[0] + '.' + reqIdParts[1]; // e.g., "1.1"
        
        // Replace jQuery-style :contains with standard DOM methods
        const allCells = document.querySelectorAll('tr td:first-child');
        let headingRow = null;
        
        // Find the cell containing the section ID
        allCells.forEach(cell => {
            if (cell.textContent.includes(sectionId)) {
                headingRow = cell.parentElement; // This is the <tr> element
                return; // Break the forEach loop
            }
        });
        
        if (headingRow) {
            const headingCell = headingRow.querySelector('td:nth-child(2)');
            if (headingCell) {
                requirementText = headingCell.textContent.trim();
                console.log("Found requirement in heading row:", requirementText);
            }
        }
    }
    
    // If we still don't have the requirement text, search more broadly
    if (!requirementText) {
        // Find the table and look for all rows
        const table = row.closest('table');
        if (table) {
            // Get all rows in the table
            const rows = table.querySelectorAll('tr');
            // Loop through rows to find the row that might contain our requirement
            for (let i = 0; i < rows.length; i++) {
                const currentRow = rows[i];
                const firstCell = currentRow.querySelector('td:first-child');
                
                // If this row has the section number in the first cell
                if (firstCell && firstCell.textContent.includes(sectionId)) {
                    // Check the next cell for the requirement text
                    const nextCell = currentRow.querySelector('td:nth-child(2)');
                    if (nextCell) {
                        requirementText = nextCell.textContent.trim();
                        console.log("Found requirement after broader search:", requirementText);
                        break;
                    }
                }
            }
        }
    }
    
    // If still not found, use a default
    if (!requirementText) {
        // Find any parent row with requirement text
        let parentRow = row.parentElement;
        while (parentRow && !requirementText) {
            if (parentRow.tagName === 'TR') {
                const reqCell = parentRow.querySelector('td:nth-child(2)');
                if (reqCell) {
                    requirementText = reqCell.textContent.trim();
                    console.log("Found requirement in parent row:", requirementText);
                }
            }
            parentRow = parentRow.parentElement;
        }
    }
    
    // Final fallback
    if (!requirementText) {
        requirementText = `Requirement ${requirementId}`;
        console.log("Using fallback requirement text:", requirementText);
    }
    
    // Find the analysis cell
    const analysisCell = document.getElementById(`analysis_${requirementId.replace('.', '_')}`);
    if (!analysisCell) return;
    
    // Find the analyze button
    const analyzeBtn = analysisCell.querySelector('.analyze-btn');
    if (!analyzeBtn) return;
    
    // Disable the button during analysis and add loading indicator
    analyzeBtn.setAttribute('disabled', 'disabled');
    
    // Add or update the spinner next to the button
    let spinner = document.getElementById(`spinner_${requirementId.replace('.', '_')}`);
    if (!spinner) {
        spinner = document.createElement('span');
        spinner.id = `spinner_${requirementId.replace('.', '_')}`;
        spinner.className = 'spinner-border spinner-border-sm ms-2';
        spinner.setAttribute('role', 'status');
        spinner.innerHTML = '<span class="visually-hidden">Loading...</span>';
        analyzeBtn.parentNode.appendChild(spinner);
    }
    
    // Add or update status text
    let statusText = document.getElementById(`status_${requirementId.replace('.', '_')}`);
    if (!statusText) {
        statusText = document.createElement('span');
        statusText.id = `status_${requirementId.replace('.', '_')}`;
        statusText.className = 'ms-2 text-muted small';
        statusText.textContent = 'Analyzing...';
        analyzeBtn.parentNode.appendChild(statusText);
    }
    
    // Remove any existing results
    const existingResults = analysisCell.querySelectorAll('.analysis-result');
    existingResults.forEach(result => result.remove());
    
    console.log("Sending analysis request for", requirementId, "with evidence:", evidence.substring(0, 50) + "...");
    
    // Send the data to the server for analysis
    fetch('/api/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            requirement_id: requirementId,
            requirement: requirementText,
            evidence: evidence
        })
    })
    .then(response => {
        console.log("Response status:", response.status);
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.explanation || 'Network response was not ok');
            });
        }
        return response.json();
    })
    .then(result => {
        console.log("Analysis result:", result);
        displayAnalysisResult(requirementId, result);
    })
    .catch(error => {
        console.error('Error during analysis:', error);
        // Remove spinner and status text
        removeAnalysisIndicators(requirementId);
        
        // Enable the analyze button
        if (analyzeBtn) {
            analyzeBtn.removeAttribute('disabled');
        }
        
        // Show error below the button
        const errorDiv = document.createElement('div');
        errorDiv.className = 'analysis-result mt-3';
        errorDiv.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                Error analyzing requirement: ${error.message}
            </div>
        `;
        analysisCell.appendChild(errorDiv);
    });
}

// Helper function to remove analysis indicators
function removeAnalysisIndicators(requirementId) {
    const spinner = document.getElementById(`spinner_${requirementId.replace('.', '_')}`);
    const statusText = document.getElementById(`status_${requirementId.replace('.', '_')}`);
    
    if (spinner) spinner.remove();
    if (statusText) statusText.remove();
}

// Function to analyze all requirements in a section
function analyzeSection(sectionId) {
    const sectionTab = document.getElementById(sectionId);
    if (!sectionTab) return;
    
    const evidenceTextareas = sectionTab.querySelectorAll('.evidence-textarea');
    let anyEvidence = false;
    
    evidenceTextareas.forEach(textarea => {
        if (textarea.value.trim() !== '') {
            anyEvidence = true;
            const requirementId = textarea.getAttribute('data-requirement-id');
            // Add slight delay between requests to avoid overloading
            setTimeout(() => {
                analyzeEvidence(requirementId);
            }, 500 * Math.random()); // Random delay between 0-500ms
        }
    });
    
    if (!anyEvidence) {
        alert('Please provide objective evidence for at least one requirement before analyzing.');
    }
}

// Function to display the analysis result
function displayAnalysisResult(requirementId, result) {
    const analysisCell = document.getElementById(`analysis_${requirementId.replace('.', '_')}`);
    if (!analysisCell) return;
    
    // Remove spinner and status text
    removeAnalysisIndicators(requirementId);
    
    // Find and enable the analyze button
    const analyzeBtn = analysisCell.querySelector('.analyze-btn');
    if (analyzeBtn) {
        analyzeBtn.removeAttribute('disabled');
    }
    
    // Determine compliance class and text
    let complianceClass = result.compliant ? 'success' : 'danger';
    let complianceText = result.compliant ? 
        '<span class="badge bg-success">Compliant</span>' : 
        '<span class="badge bg-danger">Non-Compliant</span>';
    
    // Format confidence if available
    let confidenceHtml = '';
    if ('confidence' in result) {
        const confidence = result.confidence * 100;
        confidenceHtml = `<div class="small text-muted">Confidence: ${confidence.toFixed(1)}%</div>`;
    }
    
    // Create the result container to append below the button
    const resultDiv = document.createElement('div');
    resultDiv.className = `analysis-result mt-3`;
    resultDiv.innerHTML = `
        <div class="card border-${complianceClass}">
            <div class="card-header bg-${complianceClass} bg-opacity-10 d-flex justify-content-between align-items-center">
                <div>${complianceText}</div>
                ${confidenceHtml}
            </div>
            <div class="card-body">
                <p class="card-text">${result.explanation}</p>
            </div>
        </div>
    `;
    
    // Remove any existing results
    const existingResults = analysisCell.querySelectorAll('.analysis-result');
    existingResults.forEach(result => result.remove());
    
    // Add the new result after the button
    analysisCell.appendChild(resultDiv);
    
    // Set the radio button based on the analysis result
    const radioValue = result.compliant ? 'satisfactory' : 'not_satisfactory';
    const radioButton = document.getElementById(`${radioValue}_${requirementId.replace('.', '_')}`);
    
    if (radioButton) {
        radioButton.checked = true;
    }
} 