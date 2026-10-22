import { useEffect, useState } from 'react';
import type { Bootstrap } from '@/entities/norm';
import { requestJson } from '@/shared/api';
import { Logo } from '@/shared/ui';
import { Lab } from '@/pages/reform-lab';
import { ParkingReview } from '@/pages/parking-review';
import { WorkspacePage } from '@/pages/workspace';
import { BuildInfo } from './BuildInfo';
type Tab = 'lab' | 'parking' | 'workspace' | 'bundles' | 'comparison' | 'history';
const tabs: { id: Tab; label: string; symbol: string }[] = [
  { id: 'lab', label: 'Реформа A/B/C', symbol: '⇄' },
  { id: 'parking', label: 'Парковка · Разбор текста', symbol: '◫' },
  { id: 'workspace', label: 'M0 · Решение', symbol: '◫' },
  { id: 'bundles', label: 'M0 · Пакеты норм', symbol: '▤' },
  { id: 'comparison', label: 'M0 · Сравнение', symbol: '⇄' },
  { id: 'history', label: 'M0 · История', symbol: '◷' },
];

export function App() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [tab, setTab] = useState<Tab>('lab');
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    requestJson<Bootstrap>('/api/bootstrap')
      .then((result) => {
        if (active) setData(result);
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : 'Ошибка загрузки');
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href={import.meta.env.BASE_URL} aria-label="NormLab — главная">
          <span className="brand-mark">
            N<span>·</span>
          </span>
          <span>
            NormLab<small>ЛАБОРАТОРИЯ НОРМ</small>
          </span>
        </a>
        <div className="sidebar-label">ИССЛЕДОВАНИЕ</div>
        <nav aria-label="Основная навигация">
          {tabs
            .filter((item) => item.id === 'lab' || item.id === 'parking')
            .map((item) => (
              <button
                key={item.id}
                type="button"
                className={tab === item.id ? 'nav-item active' : 'nav-item'}
                aria-current={tab === item.id ? 'page' : undefined}
                onClick={() => setTab(item.id)}
              >
                <span aria-hidden="true">{item.symbol}</span>
                {item.label}
                {item.id === 'workspace' && <i />}
              </button>
            ))}
          <details className="legacy-nav" open={tab !== 'lab'}>
            <summary>Пример M0</summary>
            <div>
              {tabs
                .filter((item) => item.id !== 'lab' && item.id !== 'parking')
                .map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={tab === item.id ? 'nav-item active' : 'nav-item'}
                    aria-current={tab === item.id ? 'page' : undefined}
                    onClick={() => setTab(item.id)}
                  >
                    <span aria-hidden="true">{item.symbol}</span>
                    {item.label}
                  </button>
                ))}
            </div>
          </details>
        </nav>
        <div className="sidebar-note">
          <span className="mini-orbit" aria-hidden="true">
            ◎
          </span>
          <strong>Проверяемая модель</strong>
          <p>Каждый вывод связан с конкретными входами и редакцией норм.</p>
        </div>
        <BuildInfo />
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="topbar-context">
            <a
              className="topbar-home"
              href={import.meta.env.BASE_URL}
              aria-label="NormLab — главная"
            >
              <Logo />
            </a>
            <div className="topbar-location">
              <span className="breadcrumb">Лаборатория</span>
              <span className="slash">/</span>
              {tabs.find((item) => item.id === tab)!.label}
            </div>
          </div>
          <span className="chip amber">
            <span className="dot" />
            Синтетические данные
          </span>
        </header>
        <main id="main">
          {!data ? (
            <section className="loading card" role="status">
              <span className="eyebrow">NORMLAB</span>
              <h1>{error ? 'Не удалось открыть лабораторию' : 'Загружаем рабочую область…'}</h1>
              {error && (
                <>
                  <p role="alert">{error}</p>
                  <button onClick={() => location.reload()}>Повторить</button>
                </>
              )}
            </section>
          ) : (
            <>
              <div className={`page-heading ${tab === 'lab' ? 'lab-page-heading' : ''}`}>
                <div>
                  <span className="eyebrow">
                    {tab === 'parking'
                      ? 'ЭКСПЕРИМЕНТ 003 / ПАРКОВОЧНЫЙ ПИЛОТ'
                      : tab === 'lab'
                        ? 'ЭКСПЕРИМЕНТ 002 / ОБЩИЕ ПРАВИЛА СМЯГЧЕНИЯ'
                        : tab === 'workspace'
                          ? 'ЭКСПЕРИМЕНТ 001 / УСЛОВНОЕ ПРЕОБРАЗОВАНИЕ'
                          : 'ИССЛЕДОВАТЕЛЬСКАЯ ЛАБОРАТОРИЯ'}
                  </span>
                  <h1>
                    {tab === 'parking'
                      ? 'Извлечь. Проверить. Исправить.'
                      : tab === 'lab'
                        ? 'Сравнивать правила. Проверять изменения.'
                        : tab === 'workspace'
                          ? 'От обстоятельств к выводу.'
                          : tab === 'bundles'
                            ? 'Нормы с явной семантикой.'
                            : tab === 'comparison'
                              ? 'Что меняет новая редакция?'
                              : 'Каждое изменение сохраняется.'}
                  </h1>
                  <p>
                    {tab === 'parking'
                      ? 'Фабула, цитаты и утверждения. Каждый шаг сохраняется.'
                      : tab === 'lab'
                        ? 'Один snapshot. Три модели. Явные последствия и границы проверки.'
                        : tab === 'workspace'
                          ? 'Установите условие, примените норму и проверьте результат.'
                          : tab === 'bundles'
                            ? 'Декларативные правила, точные версии и прослеживаемое происхождение.'
                            : tab === 'comparison'
                              ? 'Один домен случаев. Две модели. Наблюдаемые различия.'
                              : 'Выберите снимок, чтобы открыть его входы, результат и квитанцию.'}
                  </p>
                </div>
                <div className="hero-symbol" aria-hidden="true">
                  {tab === 'comparison' ? '⇄' : '∴'}
                </div>
              </div>
              <div hidden={tab !== 'lab'}>
                <Lab />
              </div>
              <div hidden={tab !== 'parking'}>
                <ParkingReview token={data.csrfToken} />
              </div>
              <div hidden={tab === 'lab' || tab === 'parking'}>
                <WorkspacePage
                  bootstrap={data}
                  tab={tab === 'lab' || tab === 'parking' ? 'workspace' : tab}
                  setTab={setTab}
                />
              </div>
              <footer>
                <span>
                  NormLab <span className="muted">/</span> исследовательский прототип
                </span>
                <span>Гарантия ограничена моделью, снимком и указанной областью.</span>
              </footer>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
