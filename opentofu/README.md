# Packaging Stack

The IaC is packaged and attached to each release using GitHub Actions.  Below is the manual procedure:

1. Zip the Iac with Archives
    ```bash
    zip -r ai-optimizer-stack.zip . -x "terraform*" ".terraform*" "*/terraform*" "*/.terraform*" "generated/*.*"
    ```