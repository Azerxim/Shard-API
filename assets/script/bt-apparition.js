document.addEventListener('DOMContentLoaded', () => {
  const $button = Array.prototype.slice.call(document.querySelectorAll('.button-apparition'), 0);

  if ($button.length > 0) {
    $button.forEach( el => {
      el.addEventListener('click', () => {
        const target = el.dataset.target;
        const $target = document.getElementById(target);

        if ($target.style.display == "none") {
          $target.style.display = "flex";
        } else {
          $target.style.display = "none";
        }
      });
    });
  }
});
