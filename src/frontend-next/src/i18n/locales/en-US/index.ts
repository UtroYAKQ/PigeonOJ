import app from './app'
import user from './user'
import home from './home'
import problems from './problems'
import admin from './admin'
import placeholder from './placeholder'
import problemSets from './problemSets'
import contests from './contests'
import teams from './teams'
import orgs from './orgs'
import community from './community'
import codes from './codes'

export default {
  ...app,
  ...user,
  ...home,
  ...problems,
  ...problemSets,
  ...contests,
  ...teams,
  ...orgs,
  ...community,
  ...codes,
  ...admin,
  ...placeholder,
}
