import { DatabaseSync } from 'node:sqlite';

export class Store {
  constructor(path) {
    this.db = new DatabaseSync(path);
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
      CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, workspace TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS threads (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), owner TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('personal','group')), agent_id TEXT NOT NULL, title TEXT NOT NULL, created_at TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS threads_project ON threads(project_id,created_at);
      CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES threads(id), project_id TEXT NOT NULL, actor_id TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','agent','system')), body TEXT NOT NULL, created_at TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS messages_thread ON messages(thread_id,created_at);
      CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, owner TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, state TEXT NOT NULL, assigned_role TEXT NOT NULL, checkpoint TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS tasks_project ON tasks(project_id,created_at);
      CREATE TABLE IF NOT EXISTS worker_jobs (job_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, owner TEXT NOT NULL, profile TEXT NOT NULL, created_at TEXT NOT NULL, parent_job_id TEXT, resume_key TEXT, checkpoint_json TEXT);
      CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, actor_id TEXT NOT NULL, event TEXT NOT NULL, entity_id TEXT NOT NULL, created_at TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS audit_project_time ON audit_events(project_id,created_at);`);
    const columns=new Set(this.db.prepare('PRAGMA table_info(worker_jobs)').all().map(x=>x.name));
    for(const [name,type] of [['parent_job_id','TEXT'],['resume_key','TEXT'],['checkpoint_json','TEXT']])if(!columns.has(name))this.db.exec(`ALTER TABLE worker_jobs ADD COLUMN ${name} ${type}`);
  }
  seedProjects(projects) {
    const insert = this.db.prepare('INSERT INTO projects(id,name,workspace) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,workspace=excluded.workspace');
    for (const p of projects) insert.run(p.id,p.name,p.workspace);
  }
  close() { this.db.close(); }
}

export const AGENTS = Object.freeze([
  {id:'director',name:'Director',role:'director',status:'LOGICAL_PROFILE'},
  {id:'developer',name:'Developer',role:'developer',status:'LOGICAL_PROFILE'},
  {id:'qa',name:'QA',role:'qa',status:'LOGICAL_PROFILE'},
  {id:'devops',name:'DevOps',role:'devops',status:'LOGICAL_PROFILE'},
  {id:'organic-marketing',name:'Organic Marketing',role:'organic_marketing',status:'EXTENSION_PROFILE'},
  {id:'seo-content',name:'SEO and Content',role:'seo_content',status:'EXTENSION_PROFILE'},
  {id:'customer-service',name:'Customer Service',role:'customer_service',status:'EXTENSION_PROFILE'},
  {id:'customer-support',name:'Customer Support',role:'customer_support',status:'EXTENSION_PROFILE'},
]);
