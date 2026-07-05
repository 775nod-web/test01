import { useState } from 'react';
import { RoleSwitcher } from './components/RoleSwitcher';
import { HqDashboardView } from './views/HqDashboardView';
import { StoreView } from './views/StoreView';
import { ProductPlanningView } from './views/ProductPlanningView';
import { DataQualityView } from './views/DataQualityView';
import type { Role } from './types';
import styles from './App.module.css';

function App() {
  const [role, setRole] = useState<Role>('hq');

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <h1 className={styles.title}>小売POS売上分析デモ</h1>
        <p className={styles.subtitle}>Gold layer (workspace.gold) をServing layer API経由で表示</p>
      </header>

      <RoleSwitcher role={role} onChange={setRole} />

      {role === 'hq' && <HqDashboardView />}
      {role === 'store' && <StoreView />}
      {role === 'product-planning' && <ProductPlanningView />}
      {role === 'data-quality' && <DataQualityView />}
    </div>
  );
}

export default App;
