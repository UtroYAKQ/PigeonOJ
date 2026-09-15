import app from './app'
import user from './user'
import home from './home'
import problems from './problems'
import admin from './admin'
import problemSets from './problemSets'
import contests from './contests'
import teams from './teams'
import orgs from './orgs'

export default {
  ...app,
  ...user,
  ...home,
  ...problems,
  ...problemSets,
  ...contests,
  ...teams,
  ...orgs,
  ...admin,
}
