/** 由当前 locale 动态生成的展示字典。 */
import type { GlobalRoleCode, ReportStatus, ReportType, SandboxNodeStatus, UserStatus } from '@/types'
import { i18n } from '@/i18n'
export type TagType = 'primary' | 'success' | 'warning' | 'danger' | 'info'
const t = (key: string): string => (i18n as unknown as { global: { t: (key: string) => string } }).global.t(key)
const labels = <T extends string>(prefix: string, values: readonly T[]) => new Proxy({} as Record<T, string>, { get: (_target, key) => t(`${prefix}.${String(key)}`) })
export const ROLE_NAME = labels('user.role', ['admin', 'tutor', 'user'] as const) as Record<GlobalRoleCode, string>
export const USER_STATUS = new Proxy({} as Record<UserStatus, { label: string; tag: TagType }>, { get: (_target,key) => ({ label:t(`user.status.${String(key)}`), tag:({active:'success',frozen:'warning',banned:'danger',deleted:'info'} as Record<string,TagType>)[String(key)]??'info' }) })
export const REPORT_STATUS = new Proxy({} as Record<ReportStatus,{label:string;tag:TagType}>, { get:(_target,key)=>({label:t(`dictionary.reportStatus.${String(key)}`),tag:({pending:'warning',handled:'success',ignored:'info'} as Record<string,TagType>)[String(key)]??'info'}) })
export const REPORT_TYPE = labels('dictionary.reportType',['problem','solution','post','comment','user'] as const) as Record<ReportType,string>
export const LOG_LEVEL = new Proxy({} as Record<string,{label:string;tag:TagType}>, {get:(_target,key)=>({label:t(`dictionary.logLevel.${String(key)}`),tag:({error:'danger',warning:'warning',fatal:'danger'}as Record<string,TagType>)[String(key)]??'info'})})
export const SANDBOX_STATUS = new Proxy({} as Record<SandboxNodeStatus,{label:string;tag:TagType}>, {get:(_target,key)=>({label:t(`dictionary.sandboxStatus.${String(key)}`),tag:({online:'success',offline:'info'}as Record<string,TagType>)[String(key)]??'info'})})
export const configCategories = () => ['site','auth_email','team','contest','sandbox','log','community'].map(value=>({value,label:t(`dictionary.category.${value}`)}))
