import client from './client'

export interface PluginTool {
  name: string
  description: string
  parameters: Record<string, unknown>
}

export interface PluginMetadata {
  name: string
  display_name: string
  description: string
  version: string
  category: string
  tools: PluginTool[]
  prompt_templates: Array<Record<string, string>>
}

export interface InstalledPlugin {
  id: string
  plugin_name: string
  plugin_version: string
  description: string | null
  config: Record<string, unknown>
  is_active: boolean
  created_at: string
}

export async function getMarketplacePlugins(): Promise<PluginMetadata[]> {
  const res = await client.get<PluginMetadata[]>('/plugins/marketplace')
  return res.data ?? []
}

export async function getInstalledPlugins(): Promise<InstalledPlugin[]> {
  const res = await client.get<InstalledPlugin[]>('/plugins/installed')
  return res.data ?? []
}

export async function installPlugin(
  pluginName: string,
): Promise<{ id: string; plugin_name: string }> {
  const res = await client.post<{ id: string; plugin_name: string }>(
    '/plugins/install',
    { plugin_name: pluginName },
  )
  return res.data
}

export async function uninstallPlugin(pluginId: string): Promise<void> {
  await client.delete(`/plugins/${pluginId}`)
}

export async function executePlugin(
  pluginName: string,
  data: { tool_name: string; arguments: Record<string, unknown> },
): Promise<Record<string, unknown>> {
  const res = await client.post<Record<string, unknown>>(
    `/plugins/${pluginName}/execute`,
    data,
  )
  return res.data
}
