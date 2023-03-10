# Elastic Cloud Image Gallery
Add autoscaler functionality based on https://github.com/xinyu910/Cloud-Image-Gallery

The project consists of 4 flask instances deployed in one EC2 instance: Frontend, ManagerAPP, AutoScaler and Memcache. Users can manually or automatically by setting some parameters to scale the memcache, such that there can be at most 7 additional memcache instances, each is hosted in a separate EC2 instance. The Frontend component allows users to upload and retrieve images from either RDS + R3 or memcache. Users can also use the UI of the Manager APP component to config memcache parameters and resize memcache pool. Manager App uses RDS to communicate with all Memcache pools for the configurations. Memcache components store images for future faster retrieval, and is responsible for publishing cloudwatch statistics metrics. Autoscaler component is responsible for the shrinking and expanding of the EC2 instances (memcache pool) after Manager APP’s resize parameters are given. 

#### Work Separation:
##### Xinyu Liu:
* FrontEnd, Manager APP UI and routes, redistribute keys functions, EC2 instances helper functions (create and delete instances), refactoring, System testing and refactoring.
##### Rahavi Selvarajan:
* Autoscaler and EC2 memcache class, Cloudwatch integration and memcache statistics, Performance testing
##### Farhan Rahman:
* Manual Scaling and Consistent MD5 hashing. Debugging Autoscaler and Performance testing



