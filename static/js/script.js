// Document Ready
$(document).ready(function() {
    // API Status Check
    $('#check-api-status').on('click', function() {
        checkApiStatus();
    });

    // Auto-check API status on page load
    setTimeout(checkApiStatus, 1000);

    // File Upload with Preview
    if ($('#file-upload').length) {
        setupFileUpload();
    }

    // Query Form
    if ($('#query-form').length) {
        setupQueryForm();
    }

    // Quick Questions
    $('.quick-question').on('click', function() {
        const question = $(this).data('question');
        $('#query-input').val(question);
        // If query form exists, trigger submit
        if ($('#query-form').length) {
            $('#query-form').submit();
        }
    });

    // Tabs
    $('a[data-bs-toggle="tab"]').on('shown.bs.tab', function (e) {
        localStorage.setItem('activeTab', $(e.target).attr('href'));
    });

    // Check if there is a previously selected tab
    let activeTab = localStorage.getItem('activeTab');
    if (activeTab) {
        $(`a[href="${activeTab}"]`).tab('show');
    }

    // Show tooltips
    $('[data-bs-toggle="tooltip"]').tooltip();
});

// Check API Status
function checkApiStatus() {
    $('#api-status-badge')
        .removeClass('bg-success bg-danger bg-secondary')
        .addClass('bg-secondary')
        .html('<i class="fas fa-spinner fa-spin"></i> Checking...');

    $.ajax({
        url: '/api-status',
        type: 'GET',
        success: function(response) {
            if (response.status) {
                $('#api-status-badge')
                    .removeClass('bg-secondary bg-danger')
                    .addClass('bg-success')
                    .html('<i class="fas fa-check-circle"></i> Available');
            } else {
                $('#api-status-badge')
                    .removeClass('bg-secondary bg-success')
                    .addClass('bg-danger')
                    .html('<i class="fas fa-times-circle"></i> Unavailable');
            }
        },
        error: function() {
            $('#api-status-badge')
                .removeClass('bg-secondary bg-success')
                .addClass('bg-danger')
                .html('<i class="fas fa-times-circle"></i> Error Checking');
        }
    });
}

// File Upload
function setupFileUpload() {
    // Preview the file when selected
    $('#file-upload').on('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const extension = file.name.split('.').pop().toLowerCase();
            
            // Update file name display
            $('#selected-file-name').text(file.name);
            
            // Show the upload button
            $('#upload-btn').removeClass('d-none');
            
            // For PDF files, show a preview
            if (extension === 'pdf' && $('#pdf-preview').length) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const pdfData = e.target.result;
                    $('#pdf-preview').html(`
                        <iframe 
                            src="${pdfData}" 
                            class="pdf-viewer" 
                            type="application/pdf">
                        </iframe>
                    `);
                };
                reader.readAsDataURL(file);
            }
            
            // For image files, show a preview
            if (['jpg', 'jpeg', 'png'].includes(extension) && $('#image-preview').length) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    $('#image-preview').html(`
                        <img src="${e.target.result}" class="img-fluid rounded" alt="Preview">
                    `);
                };
                reader.readAsDataURL(file);
            }
        }
    });
    
    // Handle form submission with progress
    $('#upload-form').on('submit', function() {
        // Show progress bar
        $('#upload-progress').removeClass('d-none');
        $('#upload-btn')
            .attr('disabled', true)
            .html('<i class="fas fa-spinner fa-spin"></i> Processing...');
    });
}

// Query Form
function setupQueryForm() {
    $('#query-form').on('submit', function(e) {
        e.preventDefault();
        
        const query = $('#query-input').val();
        if (!query) return;
        
        // Show loading state
        $('#query-btn')
            .attr('disabled', true)
            .html('<i class="fas fa-spinner fa-spin"></i> Processing...');
        
        // Show the response card with loading
        $('#query-response-card').removeClass('d-none');
        $('#query-response').html('<div class="spinner-container"><div class="spinner-border text-primary spinner" role="status"><span class="visually-hidden">Loading...</span></div></div>');
        
        // Get the job ID from the URL
        const jobId = window.location.pathname.split('/').pop();
        
        // Send the query
        $.ajax({
            url: `/query/${jobId}`,
            type: 'POST',
            data: { query: query },
            success: function(response) {
                if (response.success) {
                    // Show the response
                    $('#query-response').html(marked.parse(response.content));
                } else {
                    // Show the error
                    $('#query-response').html(`<div class="alert alert-danger">${response.error}</div>`);
                }
            },
            error: function() {
                $('#query-response').html('<div class="alert alert-danger">An error occurred while processing your query. Please try again.</div>');
            },
            complete: function() {
                // Reset button state
                $('#query-btn')
                    .attr('disabled', false)
                    .html('Ask');
            }
        });
    });
}

// Convert Markdown to HTML
function renderMarkdown() {
    document.querySelectorAll('.markdown-content').forEach(function(element) {
        element.innerHTML = marked.parse(element.textContent);
    });
} 