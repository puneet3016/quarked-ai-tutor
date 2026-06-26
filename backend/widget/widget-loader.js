(function () {
    // Inject the main widget script
    var api_url = document.currentScript ? document.currentScript.getAttribute('data-api-url') : 'http://localhost:8000';
    var s = document.createElement('script');
    s.src = api_url + '/widget/widget.js';
    s.setAttribute('data-api-url', api_url);
    document.body.appendChild(s);
})();
