# Windows Code Signing

Chrome, Edge, and Windows SmartScreen warn users when an EXE is unsigned or has no reputation. The real fix is to sign the Admin and Student CBT installers with a trusted Windows code-signing certificate.

Do not use a self-signed certificate for public downloads. It can be useful for internal testing, but it will not remove browser or SmartScreen warnings for parents, schools, or students.

## What You Need

- A trusted Windows code-signing certificate as a `.pfx` or `.p12` file.
- The certificate password.
- The certificate subject/publisher should match your business name.

For the smoothest user experience, use an EV code-signing certificate or a trusted cloud signing service. A normal OV certificate signs the file correctly, but SmartScreen may still warn until the certificate/app builds enough reputation.

## Where To Put The Certificate

Create a local folder named `certs` and put the certificate there:

```powershell
mkdir certs
```

Example:

```text
certs/SchoolDomCodeSigning.pfx
```

The repo ignores `certs/`, `.pfx`, `.p12`, `.pem`, and `.key` files so the private certificate is not committed.

## Build Signed Installers

Run this from the repo root:

```powershell
.\scripts\sign-windows-installers.ps1 -CertificatePath .\certs\SchoolDomCodeSigning.pfx
```

PowerShell will ask for the certificate password.

The script builds and signs:

- `schooldom-admin-app/release/SchoolDom-Admin-*-Setup.exe`
- `schooldom-cbt-client/release/SchoolDom-Student-CBT-*-Setup.exe`

Then it copies the final installers to:

- `media/app/admin/SchoolDomAdmin.exe`
- `media/app/student-cbt/SchoolDomCBT.exe`

Upload those two files to the same paths on the server:

```powershell
scp .\media\app\admin\SchoolDomAdmin.exe root@72.62.17.9:/root/SCHOOL-DOM/media/app/admin/SchoolDomAdmin.exe
scp .\media\app\student-cbt\SchoolDomCBT.exe root@72.62.17.9:/root/SCHOOL-DOM/media/app/student-cbt/SchoolDomCBT.exe
```

## Verify A Signed EXE

On Windows, right-click the EXE, open **Properties**, and check the **Digital Signatures** tab.

You can also use PowerShell:

```powershell
Get-AuthenticodeSignature .\media\app\admin\SchoolDomAdmin.exe
Get-AuthenticodeSignature .\media\app\student-cbt\SchoolDomCBT.exe
```

The status should be `Valid`.
