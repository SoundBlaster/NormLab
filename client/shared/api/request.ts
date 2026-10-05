export async function requestJson<T>(path: string, token?: string, body?: unknown): Promise<T> {
  const response = await fetch(
    path,
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
