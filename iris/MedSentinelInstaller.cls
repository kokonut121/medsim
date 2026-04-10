Class MedSentinel.Installer Extends %RegisteredObject
{

ClassMethod Main() As %Status
{
    set ns=..Env("MEDSENT_NAMESPACE","MEDSENT")
    set appUser=..Env("MEDSENT_APP_USER","medsent_app")
    set appPassword=..Env("MEDSENT_APP_PASSWORD","changeme")
    set fhirPath=..NormalizePath(..Env("MEDSENT_FHIR_PATH","/fhir/r4"))
    set fhirMetadata=..Env("MEDSENT_FHIR_METADATA_PACKAGE","hl7.fhir.r4.core@4.0.1")
    set fhirStrategy=..Env("MEDSENT_FHIR_STRATEGY_CLASS","HS.FHIRServer.Storage.Json.InteractionsStrategy")
    set serverName=..Env("MEDSENT_SERVER_NAME","MedSentinelFHIR")
    set walletCollection=..Env("MEDSENT_WALLET_COLLECTION","MedSentinel")
    set serviceRole=..Env("MEDSENT_SERVICE_ROLE","MedSentinel_Service")

    write !,"[MedSentinel] Ensuring audit is enabled"
    set sc=..CheckStatus(..EnsureAuditEnabled(),"Unable to enable auditing")
    if $SYSTEM.Status.IsError(sc) quit sc

    write !,"[MedSentinel] Ensuring resources and baseline roles exist"
    set sc=..CheckStatus(..EnsureResource("MedSentinel_Data","MedSentinel application data resource"),"Unable to create MedSentinel_Data")
    if $SYSTEM.Status.IsError(sc) quit sc
    set sc=..CheckStatus(..EnsureResource("MedSentinel_Wallet_Use","Use MedSentinel wallet secrets"),"Unable to create MedSentinel_Wallet_Use")
    if $SYSTEM.Status.IsError(sc) quit sc
    set sc=..CheckStatus(..EnsureResource("MedSentinel_Wallet_Edit","Edit MedSentinel wallet secrets"),"Unable to create MedSentinel_Wallet_Edit")
    if $SYSTEM.Status.IsError(sc) quit sc
    set sc=..CheckStatus(..EnsureResource("MedSentinel_FHIR_Use","Read MedSentinel FHIR resources"),"Unable to create MedSentinel_FHIR_Use")
    if $SYSTEM.Status.IsError(sc) quit sc
    set sc=..CheckStatus(..EnsureResource("MedSentinel_FHIR_Edit","Write MedSentinel FHIR resources"),"Unable to create MedSentinel_FHIR_Edit")
    if $SYSTEM.Status.IsError(sc) quit sc

    set sc=..CheckStatus(..EnsureRole("MedSentinel_SafetyOfficer","Full MedSentinel safety access","MedSentinel_Data:RWU,MedSentinel_Wallet_Use:U,MedSentinel_Wallet_Edit:W,MedSentinel_FHIR_Use:U,MedSentinel_FHIR_Edit:W",""),"Unable to create SafetyOfficer role")
    if $SYSTEM.Status.IsError(sc) quit sc
    set sc=..CheckStatus(..EnsureRole("MedSentinel_UnitManager","Scoped MedSentinel operational access","MedSentinel_Data:RW,MedSentinel_Wallet_Use:U,MedSentinel_FHIR_Use:U,MedSentinel_FHIR_Edit:W",""),"Unable to create UnitManager role")
    if $SYSTEM.Status.IsError(sc) quit sc
    set sc=..CheckStatus(..EnsureRole("MedSentinel_Auditor","Read-only MedSentinel audit access","MedSentinel_Data:R,MedSentinel_FHIR_Use:U",""),"Unable to create Auditor role")
    if $SYSTEM.Status.IsError(sc) quit sc

    write !,"[MedSentinel] Ensuring secure wallet collection exists"
    set sc=..CheckStatus(..EnsureWalletCollection(walletCollection,"MedSentinel_Wallet_Use","MedSentinel_Wallet_Edit"),"Unable to create wallet collection")
    if $SYSTEM.Status.IsError(sc) quit sc

    write !,"[MedSentinel] Ensuring namespace "_ns_" exists"
    set sc=..CheckStatus(..EnsureNamespace(ns),"Unable to install foundation namespace")
    if $SYSTEM.Status.IsError(sc) quit sc

    write !,"[MedSentinel] Ensuring FHIR namespace support and endpoint "_fhirPath_" exist"
    set sc=..CheckStatus(..EnsureFHIREndpoint(ns,fhirPath,fhirStrategy,fhirMetadata,serverName),"Unable to install FHIR endpoint")
    if $SYSTEM.Status.IsError(sc) quit sc

    set fhirRoles=..NormalizeGrantedRoles(..GetFHIRRoles(ns,fhirPath))
    write !,"[MedSentinel] Ensuring service role and application user exist"
    set sc=..CheckStatus(..EnsureRole(serviceRole,"MedSentinel backend service role","MedSentinel_Data:RWU,MedSentinel_Wallet_Use:U,MedSentinel_Wallet_Edit:W,MedSentinel_FHIR_Use:U,MedSentinel_FHIR_Edit:W",fhirRoles),"Unable to create service role")
    if $SYSTEM.Status.IsError(sc) quit sc
    set sc=..CheckStatus(..EnsureUser(appUser,appPassword,serviceRole,ns),"Unable to create application user")
    if $SYSTEM.Status.IsError(sc) quit sc

    set sc=..CheckStatus(..WriteBootstrapMarker(ns,fhirPath,serverName,appUser,walletCollection),"Unable to write bootstrap marker")
    if $SYSTEM.Status.IsError(sc) quit sc

    write !,"[MedSentinel] Bootstrap finished successfully",!
    quit 1
}

ClassMethod HandleError()
{
    write !,"[MedSentinel] Bootstrap failed: ",$ze,!
    quit 0
}

ClassMethod Env(name As %String, defaultValue As %String = "") As %String
{
    set value=$system.Util.GetEnviron(name)
    if value="" quit defaultValue
    quit value
}

ClassMethod NormalizePath(path As %String) As %String
{
    if path="" quit "/fhir/r4"
    if $extract(path,1)'="/" set path="/"_path
    quit path
}

ClassMethod CheckStatus(sc As %Status, context As %String = "")
{
    if $SYSTEM.Status.IsError(sc) write !,"[MedSentinel] "_context,!
    if $SYSTEM.Status.IsError(sc) do $system.Status.DisplayError(sc)
    quit sc
}

ClassMethod EnsureAuditEnabled() As %Status
{
    set props("AuditEnabled")=1
    quit ##class(Security.System).Modify("SYSTEM",.props)
}

ClassMethod EnsureNamespace(ns As %String) As %Status
{
    set sc=1
    set originalNS=$namespace
    set $namespace="HSLIB"
    if '##class(%SYS.Namespace).Exists(ns) kill vars
    if '##class(%SYS.Namespace).Exists(ns) set vars("Description")="MedSentinel Foundation Namespace"
    if '##class(%SYS.Namespace).Exists(ns) set sc=##class(HS.Util.Installer.Foundation).Install(ns,.vars)
    set $namespace=originalNS
    quit sc
}

ClassMethod EnsureFHIREndpoint(ns As %String, fhirPath As %String, fhirStrategy As %String, fhirMetadata As %String, serverName As %String) As %Status
{
    set sc=1
    set originalNS=$namespace
    set $namespace=ns
    do ##class(HS.FHIRServer.Installer).InstallNamespace()
    set appSc=1
    if '##class(HS.FHIRServer.Installer).CSPAppExists(fhirPath,.appObj,.appSc) do ##class(HS.FHIRServer.Installer).InstallInstance(fhirPath,fhirStrategy,fhirMetadata,"","MedSentinel FHIR repository",1,"","",serverName)
    set $namespace=originalNS
    quit sc
}

ClassMethod GetFHIRRoles(ns As %String, fhirPath As %String) As %String
{
    set originalNS=$namespace
    set $namespace=ns
    set roles=##class(HS.FHIRServer.Installer).GetCSPAppRoles(fhirPath)
    set $namespace=originalNS
    quit roles
}

ClassMethod NormalizeGrantedRoles(grantedRoles As %String) As %String
{
    if $extract(grantedRoles,1)=":" set grantedRoles=$extract(grantedRoles,2,*)
    set grantedRoles=$translate(grantedRoles,":",",")
    quit grantedRoles
}

ClassMethod EnsureResource(name As %String, description As %String) As %Status
{
    set sc=1
    if '##class(Security.Resources).Exists(name,.obj,.sc) set sc=##class(Security.Resources).Create(name,description,"")
    quit sc
}

ClassMethod EnsureRole(name As %String, description As %String, resources As %String, grantedRoles As %String) As %Status
{
    set sc=1
    if '##class(Security.Roles).Exists(name,.obj,.sc) set sc=##class(Security.Roles).Create(name,description,resources,grantedRoles) quit sc
    kill props
    set props("Description")=description
    set props("Resources")=resources
    set props("GrantedRoles")=grantedRoles
    set sc=##class(Security.Roles).Modify(name,.props)
    quit sc
}

ClassMethod EnsureWalletCollection(name As %String, useResource As %String, editResource As %String) As %Status
{
    set sc=1
    if '##class(%Wallet.Collection).Exists(name,.walletObj,.sc) kill props
    if '##class(%Wallet.Collection).Exists(name,.walletObj,.sc) set props("UseResource")=useResource
    if '##class(%Wallet.Collection).Exists(name,.walletObj,.sc) set props("EditResource")=editResource
    if '##class(%Wallet.Collection).Exists(name,.walletObj,.sc) set sc=##class(%Wallet.Collection).Create(name,.props) quit sc
    kill props
    set props("UseResource")=useResource
    set props("EditResource")=editResource
    set sc=##class(%Wallet.Collection).Modify(name,.props)
    quit sc
}

ClassMethod EnsureUser(username As %String, password As %String, roles As %String, ns As %String) As %Status
{
    set sc=1
    if '##class(Security.Users).Exists(username,.userObj,.sc) set sc=##class(Security.Users).Create(username,roles,password,"MedSentinel Service Account",ns,"","",0,1,"MedSentinel bootstrap managed service user",1,"","",.attrs,1,1) quit sc
    set roleList=roles
    set sc=##class(Security.Users).AddRoles(username,.roleList,0)
    if $SYSTEM.Status.IsError(sc) quit sc
    kill props
    set props("Enabled")=1
    set props("NameSpace")=ns
    set props("ChangePassword")=0
    set props("AccountNeverExpires")=1
    set props("PasswordNeverExpires")=1
    set sc=##class(Security.Users).Modify(username,.props)
    quit sc
}

ClassMethod WriteBootstrapMarker(ns As %String, fhirPath As %String, serverName As %String, appUser As %String, walletCollection As %String) As %Status
{
    set originalNS=$namespace
    set $namespace=ns
    set stamp=$zdatetime($horolog,3)
    set ^MedSentinel.Bootstrap("namespace")=ns
    set ^MedSentinel.Bootstrap("fhirPath")=fhirPath
    set ^MedSentinel.Bootstrap("serverName")=serverName
    set ^MedSentinel.Bootstrap("appUser")=appUser
    set ^MedSentinel.Bootstrap("walletCollection")=walletCollection
    set ^MedSentinel.Bootstrap("lastRunUTC")=stamp
    set $namespace=originalNS
    quit 1
}

}
