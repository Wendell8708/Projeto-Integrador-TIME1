
targetScope = 'resourceGroup'

@description('Nome do App Service do backend.')
param backendAppName string = 'app-caminho-vale-backend-novo'

@description('Regiao do backend.')
param backendLocation string = 'brazilsouth'

@description('Grupo de recursos do plano compartilhado.')
param planResourceGroup string = 'app-curso-lucass_group'

@description('Nome do App Service Plan existente.')
param planName string = 'ASP-appcursolucassgroup-879b'

@description('Versao do Python.')
param pythonVersion string = 'PYTHON|3.13'

@description('Comando de inicializacao do Django.')
param startupCommand string = 'gunicorn piADS04.wsgi:application --bind 0.0.0.0:8000 --timeout 600'

// Referencia o plano existente sem recria-lo.
resource existingPlan 'Microsoft.Web/serverfarms@2023-12-01' existing = {
  name: planName
  scope: resourceGroup(planResourceGroup)
}

// Configuracao declarativa do backend.
resource backend 'Microsoft.Web/sites@2023-12-01' = {
  name: backendAppName
  location: backendLocation
  kind: 'app,linux'

  properties: {
    serverFarmId: existingPlan.id
    httpsOnly: true

    siteConfig: {
      linuxFxVersion: pythonVersion
      appCommandLine: startupCommand
      minTlsVersion: '1.2'
      ftpsState: 'FtpsOnly'
      alwaysOn: false
    }
  }
}

output backendName string = backend.name
output backendUrl string = 'https://${backend.properties.defaultHostName}'
output appServicePlanId string = existingPlan.id
