---
name: categorize-job-post
description: This skill should be used when categorizing a single job posting when user provided job description text in structured JSON. Trigger when users ask to "categorize a job post", "categorize this job", "categorize this job description"
version: 0.1.0
user-invocable: true
---

## What to do

- Read job post JSON file
- Try to identify department and category
- create additional fields in the JSON for `department` and `category` and for slugified versions `department_slug` and `category_slug`
- use one of these lists to choose the best fitting department and category for the job post
- if no good fit, assign "Other" category and "Uncategorized" department
- update the source JSON file with the new fields

## Departments and Categories

### Departments

      Flight Operations
      Ground & Maintenance
      Security & Safety
      Passenger Service
      Corporate

#### Flight Operations

Airside roles involving aircraft movement and control.

##### Categories

      Pilots & First Officers
      Commercial & Cargo
      Flight Attendants
      Cabin Crew
      Air Traffic Control
      Tower & Radar
      Flight Dispatchers
      Logistics & Planning


#### Ground & Maintenance

Technical and labor roles on the tarmac.

##### Categories

      Aircraft Mechanics (A&P)
      MRO & Line Maint
      Ramp Agents
      Baggage & Cargo
      Aircraft Fuelers
      Operations
      De-Icing Crew
      Seasonal 


#### Security & Safety

TSA, Customs, and Private Security roles.

##### Categories

      TSA Officers
      Federal (DHS)
      Airport Police
      Law Enforcement
      CBP Officers


#### Passenger Service

Customer facing roles inside the terminal.

##### Categories

      Gate Agents
      Check-in & Boarding 412 Jobs
      Airline Lounge Staff
      Hospitality 88 Jobs
      Wheelchair Assist
      Special Services

#### Corporate

Office and administrative roles at airline headquarters.

##### Categories

      Finance & Accounting
      Human Resources
      Marketing & Sales
      IT & Software
      Legal & Compliance
      Executive & Management