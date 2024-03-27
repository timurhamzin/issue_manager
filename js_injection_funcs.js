function getApiUrl(url) {
    const resourceTypes = ['facult', 'profession', 'track', 'course', 'topic', 'lesson', 'task'];
    let apiUrl = '';
    let matchedResource = '';

    for (let i = 0; i < resourceTypes.length; i++) {
        const resourceRegex = new RegExp(`/${resourceTypes[i]}s?/([\\w\\-]+)(/$|$)`, 'i');
        if (resourceRegex.test(url)) {
            const resourceId = url.match(resourceRegex)[1];
            matchedResource = resourceTypes[i];
            apiUrl = `https://prestable.pierce-admin.praktikum.yandex-team.ru/content/${matchedResource}s/${resourceId}/breadcrumbs/`;
            break;
        }
    }

    if (!matchedResource) {
        throw new Error('Invalid URL or unsupported resource type');
    }

    return apiUrl;
}

// For debugging requests in a browser JS-bookmarklet
function fetchBreadcrumbsBookmarklet(url, download_to_filename) {
    try {
        const apiUrl = getApiUrl(url);
        const response = fetch(apiUrl);
        const data = response.json();

        const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
        const downloadLink = document.createElement('a');
        downloadLink.href = URL.createObjectURL(blob);
        downloadLink.download = download_to_filename || 'download.json';
        downloadLink.click();

        const jsonDisplay = document.createElement('pre');
        jsonDisplay.textContent = JSON.stringify(data, null, 2);
        document.body.appendChild(jsonDisplay);

        return {data};

    } catch (error) {
        return {error: error.message};
    }
}


function fetchBreadcrumbs(url, download_to_filename, callback) {
    try {
        const apiUrl = getApiUrl(url);
        fetch(apiUrl)
            .then(response => response.json())
            .then(data => {
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const downloadLink = document.createElement('a');
                downloadLink.href = URL.createObjectURL(blob);
                downloadLink.download = download_to_filename || 'download.json';
                downloadLink.click();
                const jsonDisplay = document.createElement('pre');
                jsonDisplay.textContent = JSON.stringify(data, null, 2);
                document.body.appendChild(jsonDisplay);
                callback({ data }); // Success callback
            })
            .catch(error => {
                callback({ error: error.message }); // Error in fetch/JSON processing
            });
    } catch (error) {
        callback({ error: error.message }); // Error in getApiUrl or other
    }
}


// Substitute callback for this function when debugging in JS console:
// function myCallback(result) {
//     console.log('Callback result:', result);
// }
function fetchApiUrl(args) {
    const { apiUrl, download_to_filename, modifyDocument = false, callback } = args;
    try {
        fetch(apiUrl)
            .then(response => response.json())
            .then(data => {
                const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
                const downloadLink = document.createElement('a');
                downloadLink.href = URL.createObjectURL(blob);
                downloadLink.download = download_to_filename || 'download.json';
                downloadLink.click();

                if (modifyDocument) {
                    const jsonDisplay = document.createElement('pre');
                    jsonDisplay.textContent = JSON.stringify(data, null, 2);
                    document.body.appendChild(jsonDisplay);
                }

                callback({data}); // Success callback
            })
            .catch(error => {
                callback({error: error.message}); // Error in fetch/JSON processing
            });
    } catch (error) {
        callback({error: error.message}); // Error in fetchApiUrl
    }
}
