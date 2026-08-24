const hamburger = document.getElementById('hamburger');
const nav = document.getElementById('nav');

hamburger.addEventListener('click', () => {
  nav.classList.toggle('open');
  hamburger.classList.toggle('active');
});

document.querySelectorAll('.nav-link').forEach(link => {
  link.addEventListener('click', () => {
    nav.classList.remove('open');
    hamburger.classList.remove('active');
  });
});

const header = document.querySelector('.header');
window.addEventListener('scroll', () => {
  header.classList.toggle('scrolled', window.scrollY > 10);
});

const secoes = document.querySelectorAll('main section[id]');
const navLinks = document.querySelectorAll('.nav-link');
const spy = new IntersectionObserver(entradas => {
  entradas.forEach(e => {
    if (e.isIntersecting) {
      navLinks.forEach(l =>
        l.classList.toggle('active', l.getAttribute('href') === '#' + e.target.id)
      );
    }
  });
}, { rootMargin: '-40% 0px -55% 0px' });
secoes.forEach(s => spy.observe(s));

const skillObs = new IntersectionObserver((entradas, obs) => {
  entradas.forEach(e => {
    if (e.isIntersecting) {
      e.target.style.width = e.target.dataset.pct + '%';
      obs.unobserve(e.target);
    }
  });
}, { threshold: 0.4 });
document.querySelectorAll('.skill-fill').forEach(f => skillObs.observe(f));

const revealObs = new IntersectionObserver((entradas, obs) => {
  entradas.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('visible');
      obs.unobserve(e.target);
    }
  });
}, { threshold: 0.12 });
document.querySelectorAll('.reveal').forEach(el => revealObs.observe(el));

const track = document.getElementById('projects-track');
const dots = document.querySelectorAll('#carousel-dots .dot');
dots.forEach((dot, i) => {
  dot.addEventListener('click', () => {
    const cards = track.children;
    if (i < cards.length) {
      track.scrollTo({ left: cards[i].offsetLeft - cards[0].offsetLeft, behavior: 'smooth' });
    }
    dots.forEach((d, j) => d.classList.toggle('active', j === i));
  });
});
track.addEventListener('scroll', () => {
  if (track.scrollWidth <= track.clientWidth) return;
  const passo = track.scrollWidth / track.children.length;
  const idx = Math.min(dots.length - 1, Math.round(track.scrollLeft / passo));
  dots.forEach((d, i) => d.classList.toggle('active', i === idx));
});

document.getElementById('btn-cv').addEventListener('click', () => {
  const cv = [
    'GABRIEL AUGUSTO',
    'Desenvolvedor Web Full-Stack',
    'gabriel.augusto4215@gmail.com | +55 (11) 91234-5678',
    '',
    'RESUMO',
    'Desenvolvedor web apaixonado por criar experiências digitais',
    'excepcionais com tecnologias modernas. Mais de 4 anos de',
    'experiência ajudando empresas e pessoas a transformarem',
    'ideias em realidade.',
    '',
    'HABILIDADES',
    'HTML (95%) | CSS (90%) | JavaScript (90%) | React.js (85%)',
    'Next.js (80%) | TypeScript (85%) | Node.js (80%)',
    'Tailwind CSS (90%) | Git (85%)',
    '',
    'PROJETOS DESTACADOS',
    '- Plataforma E-Commerce: solução full-stack com UI/UX moderno',
    '- Aplicativo de Tarefas: gerenciamento colaborativo de tarefas',
    '- Dashboard de Criptomoedas: acompanhamento em tempo real',
    '',
    'Gerado automaticamente pelo portfólio de Gabriel Augusto.'
  ].join('\n');
  const blob = new Blob([cv], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'CV-Gabriel-Augusto.txt';
  a.click();
  URL.revokeObjectURL(a.href);
  mostrarToast('📄 Download do CV iniciado!');
});

function mostrarToast(msg) {
  let t = document.querySelector('.toast');
  if (!t) {
    t = document.createElement('div');
    t.className = 'toast';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('show'), 2600);
}

document.querySelectorAll('[data-demo]').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    mostrarToast('🚀 Demonstração disponível em breve!');
  });
});

const form = document.getElementById('contact-form');
const status = document.getElementById('form-status');

form.addEventListener('submit', async e => {
  e.preventDefault();
  const dados = Object.fromEntries(new FormData(form));
  status.textContent = 'Enviando...';
  status.className = 'form-status';
  const local = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  try {
    if (local) {
      const res = await fetch('/contato', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dados)
      });
      const json = await res.json();
      if (!res.ok || !json.ok) throw new Error();
      status.textContent = '✅ ' + json.mensagem;
    } else {
      const res = await fetch('/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams(dados).toString()
      });
      if (!res.ok) throw new Error();
      status.textContent = '✅ Mensagem enviada com sucesso! Entrarei em contato em breve.';
    }
    status.classList.add('ok');
    form.reset();
  } catch {
    status.textContent = '⚠ Não foi possível enviar. Tente novamente ou me chame por e-mail.';
    status.classList.add('erro');
  }
});

document.getElementById('ano').textContent = new Date().getFullYear();
