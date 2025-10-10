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
    try {
      const updates: Record<string, Record<string, any>> = {}
      
      Object.entries(editedValues).forEach(([key, value]) => {
        const category = Object.keys(settings!).find(cat =>
          settings![cat as Category].some(s => s.key === key)
        ) as Category
        
        if (!updates[category]) updates[category] = {}
        updates[category][key] = value
      })

      const response = await fetch('/api/settings/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates }),
      })

      if (!response.ok) throw new Error('Failed to save settings')

      toast.success('Settings saved successfully')
      setEditedValues({})
      await loadSettings()
    } catch (error) {
      toast.error('Failed to save settings')
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

      toast.success('Setting reset to default')
      const newEdited = { ...editedValues }
      delete newEdited[key]
      setEditedValues(newEdited)
      await loadSettings()
    } catch (error) {
      toast.error('Failed to reset setting')
      console.error(error)
    }
  }

  const handleTestLLM = async () => {
    const llmSettings = settings?.llm || []
    const apiKey = editedValues['CODE_LLM_API_KEY'] || llmSettings.find(s => s.key === 'CODE_LLM_API_KEY')?.value
    const baseUrl = editedValues['CODE_LLM_BASE_URL'] || llmSettings.find(s => s.key === 'CODE_LLM_BASE_URL')?.value
    const model = editedValues['CODE_LLM_EXTRACTION_MODEL'] || llmSettings.find(s => s.key === 'CODE_LLM_EXTRACTION_MODEL')?.value

    if (!apiKey || apiKey.includes('••••')) {
      toast.error('Please enter a valid API key')
      return
    }

    setTesting(true)
    try {
      const response = await fetch('/api/settings/test-llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey, base_url: baseUrl, model }),
      })

      const result = await response.json()

      if (result.status === 'success') {
        toast.success(`Connection successful! Latency: ${result.latency_ms}ms`)
      } else {
        toast.error(result.message)
      }
    } catch (error) {
      toast.error('Failed to test LLM connection')
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
          <label className="flex items-center space-x-3">
            <input
              type="checkbox"
              checked={currentValue}
              onChange={(e) => handleValueChange(setting.key, e.target.checked)}
              className="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
            />
            <span className="text-sm font-medium">{setting.description}</span>
          </label>
          {isModified && (
            <button
              onClick={() => handleReset(category, setting.key)}
              className="text-xs text-gray-500 hover:text-gray-700"
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
            <label className="text-sm font-medium text-gray-700">{setting.description}</label>
            {isModified && (
              <button
                onClick={() => handleReset(category, setting.key)}
                className="text-xs text-gray-500 hover:text-gray-700"
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
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )
    }

    if (setting.options) {
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-gray-700">{setting.description}</label>
            {isModified && (
              <button
                onClick={() => handleReset(category, setting.key)}
                className="text-xs text-gray-500 hover:text-gray-700"
              >
                Reset
              </button>
            )}
          </div>
          <select
            value={currentValue || ''}
            onChange={(e) => handleValueChange(setting.key, e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {setting.options.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
      )
    }

    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-sm font-medium text-gray-700">{setting.description}</label>
          {isModified && (
            <button
              onClick={() => handleReset(category, setting.key)}
              className="text-xs text-gray-500 hover:text-gray-700"
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
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading settings...</div>
      </div>
    )
  }

  if (!settings) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-500">Failed to load settings</div>
      </div>
    )
  }

  const hasChanges = Object.keys(editedValues).length > 0

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <SettingsIcon className="w-6 h-6" />
          Settings
        </h1>
        <p className="text-gray-600 mt-1">Configure CodeDox runtime settings</p>
      </div>

      <div className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-200">
          <nav className="flex -mb-px">
            {Object.keys(CATEGORY_LABELS).map((cat) => (
              <button
                key={cat}
                onClick={() => setActiveTab(cat as Category)}
                className={`px-6 py-3 text-sm font-medium border-b-2 ${
                  activeTab === cat
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {CATEGORY_LABELS[cat as Category]}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6 space-y-6">
          {settings[activeTab].map((setting) => (
            <div key={setting.key} className="pb-4 border-b border-gray-100 last:border-0">
              {renderSettingInput(setting, activeTab)}
            </div>
          ))}

          <div className="flex items-center gap-3 pt-4">
            {activeTab === 'llm' && (
              <button
                onClick={handleTestLLM}
                disabled={testing}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50"
              >
                <TestTube2 className="w-4 h-4" />
                {testing ? 'Testing...' : 'Test Connection'}
              </button>
            )}
            
            <button
              onClick={handleSave}
              disabled={!hasChanges || saving}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Saving...' : 'Save Changes'}
            </button>

            {hasChanges && (
              <button
                onClick={() => setEditedValues({})}
                className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-800"
              >
                <RotateCcw className="w-4 h-4" />
                Discard Changes
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
