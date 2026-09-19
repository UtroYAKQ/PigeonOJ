import app from './app'
import user from './user'
import home from './home'
import problems from './problems'
import admin from './admin'
import problemSets from './problemSets'
import community from './community'
import codes from './codes'
import contests from './contests'
import teams from './teams'
import orgs from './orgs'

export default {
  ...app,
  ...user,
  ...home,
  ...problems,
  ...problemSets,
  ...community,
  ...codes,
  ...contests,
  ...teams,
  ...orgs,
  ...admin,
}
