import { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { Settings as SettingsIcon, Save, RotateCcw, TestTube2 } from 'lucide-react'

interface SettingMetadata {
  key: string
  value: any
  default_value: any
  type: string
  description: string
  is_modified: boolean
  options?: string[]
  min?: number
  max?: number
}

interface SettingsData {
  llm: SettingMetadata[]
  crawling: SettingMetadata[]
  search: SettingMetadata[]
  security: SettingMetadata[]
  api: SettingMetadata[]
  advanced: SettingMetadata[]
}

type Category = keyof SettingsData

const CATEGORY_LABELS: Record<Category, string> = {
  llm: 'LLM Configuration',
  crawling: 'Crawling',
  search: 'Search & Indexing',
  security: 'Security',
  api: 'API',
  advanced: 'Advanced',
}

export default function Settings() {
  const [activeTab, setActiveTab] = useState<Category>('llm')
  const [settings, setSettings] = useState<SettingsData | null>(null)
  const [editedValues, setEditedValues] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const response = await fetch('/api/settings')
      if (!response.ok) throw new Error('Failed to load settings')
      const data = await response.json()
      setSettings(data)
    } catch (error) {
      toast.error('Failed to load settings')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleValueChange = (key: string, value: any) => {
    setEditedValues(prev => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    const savingToast = toast.loading('Saving settings...')
    
    try {
      const updates: Record<string, Record<string, any>> = {}
      
      Object.entries(editedValues).forEach(([key, value]) => {
        const category = Object.keys(settings!).find(cat =>
          settings![cat as Category].some(s => s.key === key)
        ) as Category
        
        // Validate JSON fields before saving
        const setting = settings![category].find(s => s.key === key)
        if (setting?.type === 'json' && typeof value === 'string') {
          try {
            JSON.parse(value)
          } catch (e) {
            throw new Error(`Invalid JSON in ${key}: ${e instanceof Error ? e.message : 'Parse error'}`)
          }
        }
        
        if (!updates[category]) updates[category] = {}
        updates[category][key] = value
      })

      const response = await fetch('/api/settings/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(errorData.detail || 'Failed to save settings')
      }

      toast.dismiss(savingToast)
      toast.success('✓ Settings saved successfully', { duration: 3000 })
      setEditedValues({})
      await loadSettings()
    } catch (error) {
      toast.dismiss(savingToast)
      toast.error(`✗ Failed to save settings\n${error instanceof Error ? error.message : 'Unknown error'}`, { duration: 5000 })
      console.error(error)
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async (category: Category, key: string) => {
    try {
      const response = await fetch(`/api/settings/${category}/${key}`, {
        method: 'DELETE',
      })

      if (!response.ok) throw new Error('Failed to reset setting')

      toast.success('✓ Setting reset to default', { duration: 2000 })
      const newEdited = { ...editedValues }
      delete newEdited[key]
      setEditedValues(newEdited)
      await loadSettings()
    } catch (error) {
      toast.error(`✗ Failed to reset setting\n${error instanceof Error ? error.message : 'Unknown error'}`, { duration: 4000 })
      console.error(error)
    }
  }

  const handleTestLLM = async () => {
    const llmSettings = settings?.llm || []
    const apiKey = editedValues['CODE_LLM_API_KEY'] || llmSettings.find(s => s.key === 'CODE_LLM_API_KEY')?.value
    const baseUrl = editedValues['CODE_LLM_BASE_URL'] || llmSettings.find(s => s.key === 'CODE_LLM_BASE_URL')?.value
    const model = editedValues['CODE_LLM_EXTRACTION_MODEL'] || llmSettings.find(s => s.key === 'CODE_LLM_EXTRACTION_MODEL')?.value
    const extraParams = editedValues['CODE_LLM_EXTRA_PARAMS'] || llmSettings.find(s => s.key === 'CODE_LLM_EXTRA_PARAMS')?.value || '{}'

    setTesting(true)
    const loadingToast = toast.loading('Testing LLM connection...')
    
    try {
      const response = await fetch('/api/settings/test-llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          api_key: apiKey, 
          base_url: baseUrl, 
          model,
          extra_params: extraParams 
        }),
      })

      const result = await response.json()

      toast.dismiss(loadingToast)

      if (result.status === 'success') {
        toast.success(
          `✓ Connection successful!\nModel: ${result.model}\nLatency: ${result.latency_ms}ms`,
          { duration: 4000 }
        )
      } else {
        toast.error(
          `✗ Connection failed\n${result.message}`,
          { duration: 6000 }
        )
      }
    } catch (error) {
      toast.dismiss(loadingToast)
      toast.error(
        `✗ Failed to test LLM connection\n${error instanceof Error ? error.message : 'Unknown error'}`,
        { duration: 6000 }
      )
      console.error(error)
    } finally {
      setTesting(false)
    }
  }

  const renderSettingInput = (setting: SettingMetadata, category: Category) => {
    const currentValue = editedValues[setting.key] ?? setting.value
    const isModified = editedValues.hasOwnProperty(setting.key) || setting.is_modified

    if (setting.type === 'boolean') {
      return (
        <div className="flex items-center justify-between">
          <label className="flex items-center space-x-3 cursor-pointer">
            <input
              type="checkbox"
              checked={currentValue}
              onChange={(e) => handleValueChange(setting.key, e.target.checked)}
              className="w-4 h-4 text-primary rounded focus:ring-2 focus:ring-primary"
            />
            <span className="text-sm font-medium text-foreground">{setting.description}</span>
          </label>
          {isModified && (
            <button
              onClick={() => handleReset(category, setting.key)}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Reset
            </button>
          )}
        </div>
      )
    }

    if (setting.type === 'secret') {
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-foreground">{setting.description}</label>
            {isModified && (
              <button
                onClick={() => handleReset(category, setting.key)}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Reset
              </button>
            )}
          </div>
          <input
            type="password"
            value={currentValue || ''}
            onChange={(e) => handleValueChange(setting.key, e.target.value)}
            placeholder="Enter API key"
            className="w-full px-3 py-2 bg-background border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary text-foreground"
          />
        </div>
      )
    }

    if (setting.type === "json") {
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-foreground">
              {setting.description}
            </label>
            {isModified && (
              <button
                onClick={() => handleReset(category, setting.key)}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Reset
              </button>
            )}
          </div>
          <textarea
            value={currentValue || "{}"}
            onChange={(e) => handleValueChange(setting.key, e.target.value)}
            placeholder='{"extra_body": {"chat_template_kwargs": {"enable_thinking": false}}}'
            rows={4}
            className="w-full px-3 py-2 bg-background border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary text-foreground font-mono text-sm"
          />
          <p className="text-xs text-muted-foreground">
            Valid JSON required. Use <code className="bg-secondary px-1 rounded">:</code> not <code className="bg-secondary px-1 rounded">=</code>, and <code className="bg-secondary px-1 rounded">false</code> not <code className="bg-secondary px-1 rounded">False</code>
          </p>
        </div>
      );
    }

    if (setting.options) {
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-foreground">
              {setting.description}
            </label>
            {isModified && (
              <button
                onClick={() => handleReset(category, setting.key)}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Reset
              </button>
            )}
          </div>
          <select
            value={currentValue || ""}
            onChange={(e) => handleValueChange(setting.key, e.target.value)}
            className="w-full px-3 py-2 bg-background border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary text-foreground"
          >
            {setting.options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
      );
    }

    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-sm font-medium text-foreground">{setting.description}</label>
          {isModified && (
            <button
              onClick={() => handleReset(category, setting.key)}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Reset
            </button>
          )}
        </div>
        <input
          type={setting.type === 'integer' || setting.type === 'float' ? 'number' : 'text'}
          value={currentValue ?? ''}
          onChange={(e) => {
            const val = setting.type === 'integer' ? parseInt(e.target.value) : 
                       setting.type === 'float' ? parseFloat(e.target.value) : 
                       e.target.value
            handleValueChange(setting.key, val)
          }}
          min={setting.min}
          max={setting.max}
          className="w-full px-3 py-2 bg-background border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary text-foreground"
        />
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading settings...</div>
      </div>
    )
  }

  if (!settings) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-destructive">Failed to load settings</div>
      </div>
    )
  }

  const hasChanges = Object.keys(editedValues).length > 0

  return (
    <div className="flex flex-col h-full py-8">
      <div className="flex-1 space-y-6 max-w-5xl mx-auto w-full px-4">
        <div className="mb-6">
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <SettingsIcon className="w-8 h-8" />
            Settings
          </h1>
          <p className="text-muted-foreground mt-1">Configure CodeDox runtime settings</p>
        </div>

        <div className="bg-secondary/50 rounded-lg overflow-hidden">
          <div className="border-b border-border">
            <nav className="flex flex-wrap -mb-px">
              {Object.keys(CATEGORY_LABELS).map((cat) => (
                <button
                  key={cat}
                  onClick={() => setActiveTab(cat as Category)}
                  className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === cat
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
                  }`}
                >
                  {CATEGORY_LABELS[cat as Category]}
                </button>
              ))}
            </nav>
          </div>

          <div className="p-6 space-y-6">
            {settings[activeTab].map((setting) => (
              <div key={setting.key} className="pb-4 border-b border-border/50 last:border-0">
                {renderSettingInput(setting, activeTab)}
              </div>
            ))}

            <div className="flex items-center gap-3 pt-4 flex-wrap">
              {activeTab === 'llm' && (
                <button
                  onClick={handleTestLLM}
                  disabled={testing}
                  className="flex items-center gap-2 px-4 py-2 bg-white text-black border border-border rounded-md hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <TestTube2 className="w-4 h-4" />
                  {testing ? 'Testing...' : 'Test Connection'}
                </button>
              )}
              
              <button
                onClick={handleSave}
                disabled={!hasChanges || saving}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                <Save className="w-4 h-4" />
                {saving ? 'Saving...' : 'Save Changes'}
              </button>

              {hasChanges && (
                <button
                  onClick={() => setEditedValues({})}
                  className="flex items-center gap-2 px-4 py-2 text-muted-foreground hover:text-foreground border border-border rounded-md transition-colors"
                >
                  <RotateCcw className="w-4 h-4" />
                  Discard Changes
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
