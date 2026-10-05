export function apiUrl(path: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  return `${base}/${path.replace(/^\//, '')}`;
}

export async function requestJson<T>(path: string, token?: string, body?: unknown): Promise<T> {
  const response = await fetch(
    apiUrl(path),
    body === undefined
      ? {}
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-NormLab-Token': token ?? '' },
          body: JSON.stringify(body),
        },
  );
  const result = await response.json();
  if (!response.ok) throw new Error(result.error ?? 'Не удалось связаться с сервером.');
  return result as T;
}
