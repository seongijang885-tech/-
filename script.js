const header = document.querySelector('[data-header]');
const navToggle = document.querySelector('[data-nav-toggle]');
const navMenu = document.querySelector('[data-nav-menu]');

const syncHeaderState = () => {
  header?.classList.toggle('is-scrolled', window.scrollY > 8);
};

syncHeaderState();
window.addEventListener('scroll', syncHeaderState, { passive: true });

navToggle?.addEventListener('click', () => {
  const isOpen = navMenu.classList.toggle('is-open');
  navToggle.setAttribute('aria-expanded', String(isOpen));
  document.body.classList.toggle('nav-open', isOpen);
});

navMenu?.addEventListener('click', (event) => {
  const target = event.target;
  if (target instanceof HTMLAnchorElement) {
    navMenu.classList.remove('is-open');
    navToggle?.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('nav-open');
  }
});

const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.16 }
);

document.querySelectorAll('.reveal').forEach((element) => revealObserver.observe(element));

document.querySelector('.consult-form')?.addEventListener('submit', (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button');
  button.textContent = '상담 신청이 접수되었습니다';
  button.disabled = true;
});
