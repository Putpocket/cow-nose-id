document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('loginForm');
  const message = document.getElementById('loginMessage');

  form?.addEventListener('submit', async event => {
    event.preventDefault();
    setMessage(message, '');

    const username = document.getElementById('username')?.value.trim();
    const password = document.getElementById('password')?.value;

    if (!username || !password) {
      setMessage(message, '아이디와 비밀번호를 입력하세요.', true);
      return;
    }

    try {
      const response = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const result = await response.json();

      if (!response.ok || !result.success) {
        setMessage(message, result.error || '로그인에 실패했습니다.', true);
        return;
      }

      window.location.href = '/';
    } catch (_error) {
      setMessage(message, '서버에 연결할 수 없습니다.', true);
    }
  });
});

function setMessage(element, text, isError = false) {
  if (!element) return;
  element.textContent = text;
  element.classList.toggle('error-message', isError);
}
