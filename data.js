/* Shared data for Asa-OZ site.
 * Loaded before page scripts so `window.ASA_PRODUCTS` is available everywhere.
 */
(function () {
  'use strict';

  window.ASA_PRODUCTS = [
    { id: 'journal', name: 'Reflection Journal', type: 'physical', price: 24, img: 'https://picsum.photos/seed/asaoz-journal/600/450', desc: 'A guided journal for identity reflection and rediscovery.' },
    { id: 'print', name: 'Heritage Print', type: 'physical', price: 18, img: 'https://picsum.photos/seed/asaoz-print/600/450', desc: 'A keepsake art print rooted in heritage and memory.' },
    { id: 'session', name: 'Identity Circle Session', type: 'virtual', price: 12, img: 'https://picsum.photos/seed/asaoz-circle/600/450', desc: 'Join an online guided circle to share and be seen.' },
    { id: 'story', name: 'Cultural Storytelling Access', type: 'virtual', price: 8, img: 'https://picsum.photos/seed/asaoz-story/600/450', desc: 'Digital collection of stories that remember you.' },
    { id: 'kit', name: 'Journey Kit', type: 'physical', price: 35, img: 'https://picsum.photos/seed/asaoz-kit/600/450', desc: 'Pre-trip materials to prepare mind and heart for travel.' },
    { id: 'letter', name: 'Welcome Letter', type: 'virtual', price: 0, img: 'https://picsum.photos/seed/asaoz-letter/600/450', desc: 'A welcome letter and printable reflection guide.' }
  ];
})();
