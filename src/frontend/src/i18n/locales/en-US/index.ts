import app from './app'
import user from './user'
import home from './home'
import problems from './problems'
import admin from './admin'
import placeholder from './placeholder'
import problemSets from './problemSets'
import contests from './contests'

export default {
  ...app,
  ...user,
  ...home,
  ...problems,
  ...problemSets,
  ...contests,
  ...admin,
  ...placeholder,
}
