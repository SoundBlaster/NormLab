const { revision, builtAt } = __NORMLAB_BUILD__;
const timestamp = `${builtAt.slice(0, 10)} ${builtAt.slice(11, 16)} UTC`;

export function BuildInfo() {
  return (
    <div className="sidebar-version" aria-label="Версия приложения">
      <span>
        {import.meta.env.DEV ? 'Разработка' : 'Сборка'} ·{' '}
        {revision ? <code title={revision}>{revision.slice(0, 7)}</code> : 'commit неизвестен'}
      </span>
      <time
        dateTime={builtAt}
        title={import.meta.env.DEV ? 'Запуск dev-сервера' : 'Время сборки UI'}
      >
        {timestamp}
      </time>
    </div>
  );
}
